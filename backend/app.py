"""DocVerify backend — orchestrator, audit (L7), and persistence.

Live request path (Step 5):

    frontend
      │  POST /cases/{case_id}/documents   (one file at a time)
      ▼
    backend ── this service ──
      │  per file: POST security /scan  → collect the EvidenceBundle (safe artifacts)
      │  buffer the bundles under case_id
      │
      │  POST /cases/{case_id}/analyze
      ▼
      │  check the on-chain ledger for a case with the same document set
      │  (cache hit skips the model call) → otherwise
      │  POST model /analyze { case_id, documents:[bundles] } → CaseResult
      │  record the L7 audit hash-chain entry (backend owns durable state)
      │  persist the CaseResult to Postgres
      │  record the result on the ledger for future cache hits
      ▼
    returns the CaseResult to the frontend

The backend never touches original PDF bytes beyond forwarding them to the
security gateway; only ``security`` is allowed to parse hostile input.  The
old ``security → model /predict`` stub hop is retired — orchestration lives
here now.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import audit
import db
import ledger_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docverify.backend")

app = FastAPI(
    title="DocVerify API",
    description="Orchestrates the security gateway and the ML model, and persists case results.",
    version="2.0.0",
)


# ---------------------------------------------------------------------------
# Service discovery
# ---------------------------------------------------------------------------

def _in_docker() -> bool:
    return os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in {"1", "true", "yes"}


def resolve_security_gateway_url() -> str:
    configured = os.getenv("SECURITY_GATEWAY_URL") or os.getenv("SANDBOX_SERVICE_URL")
    if configured:
        return configured
    return "http://security:8002" if _in_docker() else "http://127.0.0.1:8002"


def resolve_security_gateway_path() -> str:
    return os.getenv("SECURITY_GATEWAY_PATH") or os.getenv("SANDBOX_SERVICE_PATH") or "/scan"


def resolve_model_service_url() -> str:
    configured = os.getenv("MODEL_SERVICE_URL")
    if configured:
        return configured
    return "http://model:8001" if _in_docker() else "http://127.0.0.1:8001"


def resolve_model_analyze_path() -> str:
    return os.getenv("MODEL_ANALYZE_PATH") or "/analyze"


SECURITY_SCAN_URL = f"{resolve_security_gateway_url().rstrip('/')}{resolve_security_gateway_path()}"
MODEL_ANALYZE_URL = f"{resolve_model_service_url().rstrip('/')}{resolve_model_analyze_path()}"


# ---------------------------------------------------------------------------
# Per-case bundle buffer (in-memory).
#
# Holds the EvidenceBundles for a case between the per-file /documents scans
# and the /analyze call.  In-memory is adequate for a single-instance dev
# deploy; a multi-replica production backend would move this to Postgres or an
# object store (the bundles carry base64 page PNGs).
# ---------------------------------------------------------------------------

case_bundles: dict[str, list[dict[str, Any]]] = {}
latest_results: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Per-case analysis progress (in-memory, single-instance dev — see buffer note
# above). Phases are real orchestration transitions inside /analyze, not a
# cosmetic timer: the frontend polls GET /cases/{id}/progress and advances its
# step list only when the backend actually moves to the next phase.
# ---------------------------------------------------------------------------

ANALYZE_PHASES = [
    "checking_ledger",
    "running_pipeline",
    "recording_audit",
    "persisting_case",
    "anchoring_ledger",
    "done",
]

case_progress: dict[str, dict[str, Any]] = {}


def _set_progress(case_id: str, phase: str, **extra: Any) -> None:
    case_progress[case_id] = {"phase": phase, "updated_at": time.time(), **extra}


# ---------------------------------------------------------------------------
# CORS (frontend dev origins)
# ---------------------------------------------------------------------------

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


@app.on_event("startup")
def _startup() -> None:
    logger.info("Security scan URL:  %s", SECURITY_SCAN_URL)
    logger.info("Model analyze URL:  %s", MODEL_ANALYZE_URL)
    if db.is_enabled():
        db.init_db()
    else:
        logger.info("DATABASE_URL unset — case persistence disabled (results in-memory only)")


# ---------------------------------------------------------------------------
# HTTP helpers (urllib keeps the backend dependency-free beyond FastAPI)
# ---------------------------------------------------------------------------

def _scan_document(raw_bytes: bytes, filename: str, content_type: str, request_id: str) -> dict[str, Any]:
    """POST original bytes to the security gateway; return its EvidenceBundle.

    Propagates the gateway's rejection (4xx) verbatim so the frontend can render
    the Layer-0 block, and maps connectivity failures to 503.
    """
    boundary = uuid.uuid4().hex
    safe_filename = filename.replace('"', "_")
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + raw_bytes + tail

    request = urllib.request.Request(
        SECURITY_SCAN_URL,
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
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(error_body).get("detail", error_body)
        except Exception:
            detail = error_body or f"Security gateway returned HTTP {exc.code}."
        raise HTTPException(status_code=exc.code, detail=detail)
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Security gateway unavailable at {SECURITY_SCAN_URL}: {exc.reason}",
        )


def _analyze_case(case_id: str, bundles: list[dict[str, Any]], request_id: str) -> dict[str, Any]:
    """POST the collected bundles to the model service; return its CaseResult."""
    payload = json.dumps({"case_id": case_id, "documents": bundles}).encode("utf-8")
    request = urllib.request.Request(
        MODEL_ANALYZE_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": request_id,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(error_body).get("detail", error_body)
        except Exception:
            detail = error_body or f"Model service returned HTTP {exc.code}."
        raise HTTPException(status_code=exc.code, detail=detail)
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model service unavailable at {MODEL_ANALYZE_URL}: {exc.reason}",
        )


def _case_content_hash(bundles: list[dict[str, Any]]) -> str:
    """Stable hash over a case's document hashes; the on-chain ledger cache key.

    A CaseResult covers the whole case (multiple documents scored together —
    e.g. INCOME_MISMATCH compares across documents), so the natural cache
    granularity is the case's document set, not any single file.
    """
    doc_hashes = sorted(b.get("sha256", "") for b in bundles)
    return hashlib.sha256("".join(doc_hashes).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "Welcome to DocVerify API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Case orchestration
# ---------------------------------------------------------------------------

class DocumentAccepted(BaseModel):
    status: str
    case_id: str
    filename: str | None
    sha256: str
    page_count: int
    pdf_anomaly_count: int
    documents_buffered: int


@app.post("/cases/{case_id}/documents", response_model=DocumentAccepted)
async def add_case_document(
    case_id: str,
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    """Scan one uploaded file and buffer its EvidenceBundle under the case.

    On a Layer-0 rejection the security gateway's 4xx propagates unchanged, so
    a malicious/corrupt file never enters the case buffer.
    """
    request_id = x_request_id or uuid.uuid4().hex
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        bundle = _scan_document(
            contents,
            file.filename or "upload.pdf",
            file.content_type or "application/octet-stream",
            request_id,
        )
        # Tag the bundle with the uploader's category so the analysed result can
        # be grouped back into the UI's land/legal/financial columns.
        if category:
            bundle["category"] = category

        case_bundles.setdefault(case_id, []).append(bundle)

        return DocumentAccepted(
            status=bundle.get("status", "CLEAN_AND_SANITIZED"),
            case_id=case_id,
            filename=bundle.get("filename") or file.filename,
            sha256=bundle.get("sha256", ""),
            page_count=int(bundle.get("page_count", 0) or 0),
            pdf_anomaly_count=len(bundle.get("pdf_anomalies", []) or []),
            documents_buffered=len(case_bundles[case_id]),
        )
    finally:
        await file.close()


@app.post("/cases/{case_id}/analyze")
async def analyze_case(
    case_id: str,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    """Run the full analysis over the case's buffered bundles.

    Ledger cache check (by case document-set hash) → model analysis (on a
    miss) → L7 audit hash-chain (recorded here, in the backend) → Postgres
    persistence → record on the ledger → return the CaseResult.
    """
    request_id = x_request_id or uuid.uuid4().hex
    bundles = case_bundles.get(case_id)
    if not bundles:
        raise HTTPException(
            status_code=400,
            detail=f"No scanned documents buffered for case {case_id}. Upload documents first.",
        )

    try:
        _set_progress(case_id, "checking_ledger", documents=len(bundles))
        case_hash = _case_content_hash(bundles)
        # Off the event loop: ledger_client makes a blocking RPC call, and a
        # concurrent GET /progress poll must still be served while this runs.
        cached_result = await asyncio.to_thread(ledger_client.check_document, case_hash)
        ledger_cache_hit = cached_result is not None

        if ledger_cache_hit:
            result = cached_result
        else:
            _set_progress(case_id, "running_pipeline", documents=len(bundles))
            # Off the event loop: this is the long real call (OCR, forensics,
            # cross-doc checks, registry correlation, scoring all happen in
            # the model service during this one HTTP round trip).
            result = await asyncio.to_thread(_analyze_case, case_id, bundles, request_id)

        _set_progress(case_id, "recording_audit")
        # Layer 7 — audit trail now lives in the backend, next to persistence.
        document_hashes = {
            d.get("filename", f"doc_{i}"): d.get("sha256", "")
            for i, d in enumerate(result.get("documents", []))
        }
        try:
            entry = audit.record(
                case_id,
                document_hashes,
                int(result.get("fraud_score", 0) or 0),
                str(result.get("risk_band", "")),
            )
            result["audit_entry"] = entry
        except Exception as exc:  # audit must never sink a completed analysis
            logger.warning("Audit record failed for case %s: %s", case_id, exc)

        _set_progress(case_id, "persisting_case")
        persisted = db.save_case_result(result)
        result["persisted"] = persisted
        latest_results[case_id] = result

        if not ledger_cache_hit:
            _set_progress(case_id, "anchoring_ledger")
            await asyncio.to_thread(
                ledger_client.record_document,
                file_hash_hex=case_hash,
                fraud_score=int(result.get("fraud_score", 0) or 0),
                risk_band=str(result.get("risk_band", "")),
                case_id=case_id,
                result_json=json.dumps(result),
            )

        _set_progress(case_id, "done", ledger_cache_hit=ledger_cache_hit)
    except Exception as exc:
        _set_progress(case_id, "error", detail=str(exc))
        raise
    finally:
        # The buffer's job is done; free the (page-PNG-heavy) bundles.
        case_bundles.pop(case_id, None)

    logger.info(
        "Case %s analyzed: score=%s band=%s persisted=%s ledger_cache_hit=%s",
        case_id, result.get("fraud_score"), result.get("risk_band"), persisted, ledger_cache_hit,
    )
    return result


@app.get("/cases/{case_id}/progress")
async def get_case_progress(case_id: str):
    """Poll target for the analyzing UI — real phase transitions, not a timer.

    Returns {"phase": "idle"} for a case that hasn't started /analyze yet, so
    the frontend can start polling before or after issuing the POST without
    a 404 race.
    """
    return case_progress.get(case_id, {"phase": "idle"})


@app.get("/cases/{case_id}/result")
async def get_case_result(case_id: str):
    """Return a previously analyzed CaseResult (from Postgres, else in-memory)."""
    result = db.get_case_result(case_id) or latest_results.get(case_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No result found for case {case_id}.")
    return result


# ---------------------------------------------------------------------------
# Deprecated single-file passthrough (pre-Step-5 clients).
# Scans one file and returns the EvidenceBundle; does not analyze or persist.
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    request_id = x_request_id or uuid.uuid4().hex
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        bundle = _scan_document(
            contents,
            file.filename or "upload.pdf",
            file.content_type or "application/octet-stream",
            request_id,
        )
        return {**bundle, "request_id": request_id}
    finally:
        await file.close()


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
