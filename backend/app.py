import os
from typing import Any
import urllib.error
import urllib.request
import uuid
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi import Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="DocVerify API",
    description="Simple FastAPI server that forwards uploads to a sandbox microservice",
    version="1.0.0"
)


def resolve_security_gateway_url() -> str:
    configured_url = os.getenv("SECURITY_GATEWAY_URL") or os.getenv("SANDBOX_SERVICE_URL")
    if configured_url:
        return configured_url

    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in {"1", "true", "yes"}:
        return "http://security:8002"

    return "http://127.0.0.1:8002"


def resolve_security_gateway_path() -> str:
    return os.getenv("SECURITY_GATEWAY_PATH") or os.getenv("SANDBOX_SERVICE_PATH") or "/scan"


SECURITY_GATEWAY_URL = resolve_security_gateway_url()
SECURITY_GATEWAY_PATH = resolve_security_gateway_path()


class SandboxResultPayload(BaseModel):
    request_id: str
    filename: str | None = None
    status: str = "safe"
    data: dict[str, Any] | list[Any] | str | None = None
    message: str | None = None


pending_uploads: dict[str, dict[str, Any]] = {}
latest_sandbox_results: dict[str, SandboxResultPayload] = {}

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to DocVerify API",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        request_id = uuid.uuid4().hex
        boundary = uuid.uuid4().hex
        content_type = file.content_type or "application/octet-stream"
        safe_filename = (file.filename or "upload").replace('"', "_")

        pending_uploads[request_id] = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(contents),
            "status": "forwarded_to_security_gateway",
        }

        multipart_head = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{safe_filename}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        multipart_tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = multipart_head + contents + multipart_tail

        target_url = f"{SECURITY_GATEWAY_URL.rstrip('/')}{SECURITY_GATEWAY_PATH}"
        request = urllib.request.Request(
            target_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
                "X-Request-ID": request_id,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response_body = response.read().decode("utf-8")
                try:
                    gateway_result = json.loads(response_body)
                except Exception:
                    gateway_result = response_body

                pending_uploads[request_id]["status"] = "processed"

                return gateway_result

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            try:
                error_json = json.loads(error_body)
                # If Security Gateway returned structured rejection JSON (e.g. detail field or status REJECTED)
                detail = error_json.get("detail", error_json)
            except Exception:
                detail = error_body or f"Security Gateway returned HTTP {exc.code}."
            
            raise HTTPException(status_code=exc.code, detail=detail)

        except urllib.error.URLError as exc:
            pending_uploads.pop(request_id, None)
            raise HTTPException(
                status_code=503,
                detail=f"Security Gateway unavailable at {target_url}: {exc.reason}",
            )
    finally:
        await file.close()


@app.post("/sandbox/result")
async def receive_sandbox_result(payload: SandboxResultPayload, request_id: str | None = Header(default=None, alias="X-Request-ID")):
    resolved_request_id = payload.request_id or request_id

    if not resolved_request_id:
        raise HTTPException(status_code=400, detail="Missing request_id for sandbox callback.")

    latest_sandbox_results[resolved_request_id] = payload.model_copy(update={"request_id": resolved_request_id})

    if resolved_request_id in pending_uploads:
        pending_uploads[resolved_request_id]["status"] = payload.status
        pending_uploads[resolved_request_id]["sandbox_result"] = payload.model_dump()

    return {
        "message": "Sandbox result received.",
        "request_id": resolved_request_id,
        "stored": True,
    }


@app.get("/sandbox/result/{request_id}")
async def get_sandbox_result(request_id: str):
    result = latest_sandbox_results.get(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sandbox result not found.")

    return result.model_dump()


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",   # Listen on all interfaces
        port=8000,
        reload=True
    )