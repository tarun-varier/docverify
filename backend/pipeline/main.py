"""DocVerify Real-Time — FastAPI entry point (Layer 6 dashboard + API).

Run with:  uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import audit, pipeline
from .models import CaseResult

app = FastAPI(title="DocVerify Real-Time", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_FILES = 12
MAX_BYTES = 25 * 1024 * 1024  # per file
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


@app.post("/api/analyze", response_model=CaseResult)
async def analyze(files: list[UploadFile] = File(...)) -> CaseResult:
    if not files:
        raise HTTPException(400, "Upload at least one document.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"At most {MAX_FILES} documents per case.")

    bundle: list[tuple[str, bytes]] = []
    for f in files:
        name = Path(f.filename or "document").name
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(400, f"Unsupported file type: {name}")
        payload = await f.read()
        if len(payload) > MAX_BYTES:
            raise HTTPException(400, f"{name} exceeds the 25 MB limit.")
        bundle.append((name, payload))

    return pipeline.analyze_case(bundle)


@app.get("/api/audit/verify")
def audit_verify() -> dict:
    intact, entries = audit.verify_chain()
    return {"intact": intact, "entries": entries}


@app.get("/")
def index():
    # The bundled dashboard is optional; the API is usable without it.
    if (STATIC_DIR / "index.html").is_file():
        return FileResponse(STATIC_DIR / "index.html")
    return {"service": "DocVerify Real-Time", "status": "running", "docs": "/docs"}


# Only mount static assets when they are present — StaticFiles raises at import
# time if the directory is missing, which would break the whole app.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
