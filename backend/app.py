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

SANDBOX_SERVICE_URL = os.getenv("SANDBOX_SERVICE_URL", "http://localhost:8001")
SANDBOX_SERVICE_PATH = os.getenv("SANDBOX_SERVICE_PATH", "/api/scan")


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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
            "status": "forwarded_to_sandbox",
        }

        multipart_head = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{safe_filename}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        multipart_tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = multipart_head + contents + multipart_tail

        request = urllib.request.Request(
            f"{SANDBOX_SERVICE_URL.rstrip('/')}{SANDBOX_SERVICE_PATH}",
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
                response_body = response.read()
                response_content_type = response.headers.get("Content-Type", "")

                if "application/json" in response_content_type.lower() and response_body:
                    sandbox_result = response_body.decode("utf-8")
                elif response_body:
                    sandbox_result = response_body.decode("utf-8", errors="ignore")
                else:
                    sandbox_result = None

                pending_uploads[request_id]["status"] = "waiting_for_callback"

                return {
                    "message": "File forwarded to sandbox successfully.",
                    "request_id": request_id,
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(contents),
                    "sandbox_result": sandbox_result,
                }
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            detail = error_body or f"Sandbox service returned HTTP {exc.code}."
            raise HTTPException(status_code=exc.code, detail=detail)
        except urllib.error.URLError as exc:
            pending_uploads.pop(request_id, None)
            raise HTTPException(
                status_code=503,
                detail=f"Sandbox service unavailable at {SANDBOX_SERVICE_URL}{SANDBOX_SERVICE_PATH}: {exc.reason}",
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