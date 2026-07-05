import logging

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from pipeline.analyze import EvidenceBundleIn, analyze_bundles
from pipeline.models import CaseResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_model_service")

app = FastAPI(
    title="DocVerify ML Fraud Detection Model Service",
    description="Microservice running the document fraud-detection pipeline over safe artifacts.",
    version="2.0.0",
)


class AnalyzeRequest(BaseModel):
    """A case: the EvidenceBundles the security service produced, one per file."""

    case_id: str | None = None
    documents: list[EvidenceBundleIn] = Field(default_factory=list)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-model", "port": 8001}


@app.post("/analyze", response_model=CaseResult)
async def analyze_case_endpoint(
    request: AnalyzeRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    """Analyze a case of safe EvidenceBundles and return a full CaseResult.

    This is the real fraud-detection path: OCR fallback, field extraction,
    classification, rehydrated PDF-native forensics, deferred backdating, ELA,
    cross-document checks, registry correlation, and scoring.  The L7 audit
    entry is left empty here and recorded by the backend service.
    """
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided for analysis.")

    logger.info(
        f"Analyzing case with {len(request.documents)} document(s). Request ID: {x_request_id}"
    )
    return analyze_bundles(request.documents, case_id=request.case_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
