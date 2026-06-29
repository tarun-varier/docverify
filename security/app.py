import os
import shutil
import tempfile
import uuid
from typing import List
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from utils import (
    get_logger,
    calculate_sha256,
    validate_pdf_header,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    ML_SERVICE_URL,
    ALLOWED_MIME_TYPES,
)
from scanner import scan_pdf
from converter import convert_pdf_to_pngs

logger = get_logger()

app = FastAPI(
    title="Layer 0 PDF Security Gateway",
    description="Offline microservice for static PDF threat analysis and Content Disarm and Reconstruction (CDR).",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "security-gateway", "port": 8002}


@app.post("/scan")
async def scan_and_process_pdf(request: Request, file: UploadFile = File(...)):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    extra_log = {"request_id": request_id, "filename": file.filename}
    logger.info("Upload received by Security Gateway", extra={"extra_data": extra_log})

    # 1. Validate file extension and MIME type
    filename = file.filename or "uploaded.pdf"
    if not filename.lower().endswith(".pdf"):
        logger.warning("Rejected file with invalid extension", extra={"extra_data": extra_log})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "REJECTED", "threat": "HIGH", "findings": ["Invalid file extension. Only .pdf allowed."]}
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
        logger.warning(f"Rejected unallowed MIME type: {content_type}", extra={"extra_data": extra_log})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "REJECTED", "threat": "HIGH", "findings": [f"Invalid MIME type: {content_type}. Only application/pdf allowed."]}
        )

    # 2. Create isolated temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"sec_gw_{request_id}_")
    pdf_file_path = os.path.join(temp_dir, "input.pdf")

    try:
        # Read and check file size limit
        contents = await file.read()
        file_size = len(contents)
        extra_log["file_size_bytes"] = file_size

        if file_size == 0:
            logger.warning("Rejected empty file upload", extra={"extra_data": extra_log})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "REJECTED", "threat": "HIGH", "findings": ["Uploaded file is empty."]}
            )

        if file_size > MAX_FILE_SIZE_BYTES:
            logger.warning(f"File size {file_size} exceeds max limit of {MAX_FILE_SIZE_MB}MB", extra={"extra_data": extra_log})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "REJECTED", "threat": "HIGH", "findings": [f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB}MB."]}
            )

        # Save PDF temporarily
        with open(pdf_file_path, "wb") as f:
            f.write(contents)

        # 3. Calculate SHA-256 hash & validate PDF magic bytes
        file_hash = calculate_sha256(pdf_file_path)
        extra_log["sha256"] = file_hash
        logger.info(f"File hash calculated: {file_hash}", extra={"extra_data": extra_log})

        if not validate_pdf_header(pdf_file_path):
            logger.warning("PDF header magic byte check failed (%PDF- expected)", extra={"extra_data": extra_log})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "REJECTED", "threat": "HIGH", "findings": ["Invalid PDF magic header bytes."]}
            )

        # 4. Run Static PDF Analysis via scanner.py
        is_clean, findings = scan_pdf(pdf_file_path)
        if not is_clean:
            extra_log["findings"] = findings
            logger.warning("Suspicious objects detected. PDF rejected.", extra={"extra_data": extra_log})
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "REJECTED",
                    "threat": "HIGH",
                    "findings": findings
                }
            )

        logger.info("PDF static scanner passed successfully. Proceeding to CDR.", extra={"extra_data": extra_log})

        # 5. Perform Content Disarm and Reconstruction (CDR)
        png_output_dir = os.path.join(temp_dir, "png_pages")
        try:
            png_paths = convert_pdf_to_pngs(pdf_file_path, png_output_dir)
        except Exception as conv_err:
            logger.error(f"CDR conversion failed: {conv_err}", extra={"extra_data": extra_log})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "REJECTED", "threat": "HIGH", "findings": [f"CDR conversion error: {str(conv_err)}"]}
            )

        logger.info(f"PDF converted to {len(png_paths)} PNG images and original PDF deleted.", extra={"extra_data": extra_log})

        # 6. Forward PNG images to ML Model Service (Port 8001)
        files_to_send = []
        file_handles = []
        try:
            for png_path in png_paths:
                fh = open(png_path, "rb")
                file_handles.append(fh)
                files_to_send.append(("files", (os.path.basename(png_path), fh, "image/png")))

            logger.info(f"Forwarding PNG images to ML Model Service at {ML_SERVICE_URL}", extra={"extra_data": extra_log})
            
            try:
                ml_response = requests.post(
                    ML_SERVICE_URL,
                    files=files_to_send,
                    headers={"X-Request-ID": request_id},
                    timeout=60
                )
            except requests.exceptions.Timeout:
                logger.error("Timeout connecting to ML model service", extra={"extra_data": extra_log})
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="ML model service timed out.")
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Error connecting to ML model service: {req_err}", extra={"extra_data": extra_log})
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"ML model service unavailable: {str(req_err)}")

        finally:
            for fh in file_handles:
                fh.close()

        # Parse ML model response
        try:
            ml_data = ml_response.json()
        except Exception:
            ml_data = ml_response.text

        logger.info("Received response from ML model service", extra={"extra_data": {"ml_status_code": ml_response.status_code}})

        return JSONResponse(status_code=ml_response.status_code, content=ml_data)

    finally:
        # 7. Automatic Cleanup of temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir}", extra={"extra_data": extra_log})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
