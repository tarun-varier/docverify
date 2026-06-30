from __future__ import annotations

import base64
import gc
import logging
from io import BytesIO
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader

logger = logging.getLogger("security_gateway")


app = FastAPI(
    title="Layer 0 Security Sandbox",
    description="Offline PDF static analysis and CDR sandbox.",
    version="1.0.0",
)


def _resolve_object(value: Any) -> Any:
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def _reject_if_malicious(reader: PdfReader) -> None:
    root = _resolve_object(reader.trailer.get("/Root"))
    if not isinstance(root, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF structure: root catalog is malformed",
        )

    names = _resolve_object(root.get("/Names"))
    if isinstance(names, dict) and "/JavaScript" in names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malicious payload detected and dropped: root catalog contains /Names -> /JavaScript",
        )

    if "/OpenAction" in root:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malicious payload detected and dropped: root catalog contains /OpenAction",
        )

    for page_index, page in enumerate(reader.pages, start=1):
        page_obj = _resolve_object(page)
        if not isinstance(page_obj, dict):
            continue

        if "/AA" in page_obj:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Malicious payload detected and dropped: page {page_index} contains /AA",
            )

        annotations = _resolve_object(page_obj.get("/Annots"))
        if not annotations:
            continue

        if not isinstance(annotations, list):
            annotations = [annotations]

        for annotation in annotations:
            annotation_obj = _resolve_object(annotation)
            if not isinstance(annotation_obj, dict):
                continue

            action = _resolve_object(annotation_obj.get("/A"))
            if isinstance(action, dict):
                action_type = str(action.get("/S", ""))
                if action_type in {"/JavaScript", "/Launch"}:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "Malicious payload detected and dropped: page "
                            f"{page_index} annotation action type {action_type}"
                        ),
                    )


def _image_to_base64_png(image: Image.Image) -> str:
    buffer = BytesIO()
    try:
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    finally:
        buffer.close()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/sanitize")
async def sanitize_pdf(file: UploadFile = File(...)) -> JSONResponse:
    if file.content_type not in {"application/pdf", "application/octet-stream", None}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF",
        )

    try:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        try:
            reader = PdfReader(BytesIO(raw_bytes), strict=False)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF: {exc}",
            ) from exc

        if getattr(reader, "is_encrypted", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encrypted PDFs are not supported",
            )

        try:
            _ = len(reader.pages)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF: {exc}",
            ) from exc

        _reject_if_malicious(reader)

        images = []
        try:
            images = convert_from_bytes(raw_bytes)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to sanitize PDF: {exc}",
            ) from exc

        try:
            pages = [_image_to_base64_png(image) for image in images]
        finally:
            # Explicitly close all PIL images to free memory
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass
            images.clear()
            del images
            gc.collect()

        return JSONResponse(content={"status": "CLEAN_AND_SANITIZED", "pages": pages})

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to process uploaded PDF: {exc}",
        ) from exc


@app.post("/scan")
async def scan_pdf_endpoint(
    file: UploadFile = File(...),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> JSONResponse:
    """
    Main scan endpoint called by the backend.
    Performs static analysis, CDR sanitization, and forwards page images to the ML model.
    """
    if file.content_type not in {"application/pdf", "application/octet-stream", None}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF",
        )

    images = []
    try:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        # Step 1: Parse and validate PDF structure
        try:
            reader = PdfReader(BytesIO(raw_bytes), strict=False)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF: {exc}",
            ) from exc

        if getattr(reader, "is_encrypted", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Encrypted PDFs are not supported",
            )

        try:
            num_pages = len(reader.pages)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or corrupted PDF: {exc}",
            ) from exc

        # Step 2: Reject malicious content
        _reject_if_malicious(reader)

        # Step 3: CDR — Convert PDF pages to images (sanitized flat pixels)
        try:
            images = convert_from_bytes(raw_bytes)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to render PDF pages: {exc}",
            ) from exc

        # Step 4: Forward page images to ML model for fraud detection
        import urllib.request
        import urllib.error
        import json as json_mod
        from utils import ML_SERVICE_URL

        ml_result = None
        try:
            import uuid
            boundary = uuid.uuid4().hex
            body_parts = []

            for idx, image in enumerate(images):
                buf = BytesIO()
                try:
                    image.save(buf, format="PNG")
                    png_bytes = buf.getvalue()
                finally:
                    buf.close()

                body_parts.append(
                    f"--{boundary}\r\n"
                    f"Content-Disposition: form-data; name=\"files\"; filename=\"page_{idx + 1}.png\"\r\n"
                    f"Content-Type: image/png\r\n\r\n".encode("utf-8")
                    + png_bytes
                    + b"\r\n"
                )

            body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
            body = b"".join(body_parts)

            ml_request = urllib.request.Request(
                ML_SERVICE_URL,
                data=body,
                method="POST",
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Accept": "application/json",
                    **({
                        "X-Request-ID": x_request_id
                    } if x_request_id else {}),
                },
            )

            with urllib.request.urlopen(ml_request, timeout=30) as response:
                ml_result = json_mod.loads(response.read().decode("utf-8"))

        except Exception as ml_err:
            logger.warning(f"ML model call failed: {ml_err}")
            ml_result = {
                "status": "ML_UNAVAILABLE",
                "error": str(ml_err),
            }

        # Step 5: Build response with sanitized page previews
        try:
            pages_b64 = [_image_to_base64_png(image) for image in images]
        finally:
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass
            images.clear()
            del images
            images = []  # prevent finally block from double-closing
            gc.collect()

        return JSONResponse(content={
            "status": "CLEAN_AND_SANITIZED",
            "pages": pages_b64,
            "page_count": num_pages,
            "ml_prediction": ml_result,
            "request_id": x_request_id,
        })

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to process uploaded PDF: {exc}",
        ) from exc
    finally:
        # Safety net: close any remaining images
        for img in images:
            try:
                img.close()
            except Exception:
                pass
        gc.collect()
