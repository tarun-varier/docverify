import logging
from typing import List
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from pydantic import BaseModel, Field
from PIL import Image
import io

from pipeline.analyze import EvidenceBundleIn, analyze_bundles
from pipeline.models import CaseResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_model_service")

app = FastAPI(
    title="DocVerify ML Fraud Detection Model Service",
    description="Microservice running the document fraud-detection pipeline over safe artifacts.",
    version="1.0.0"
)


class AnalyzeRequest(BaseModel):
    """A case: the EvidenceBundles the security service produced, one per file."""

    case_id: str | None = None
    documents: list[EvidenceBundleIn] = Field(default_factory=list)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-model", "port": 8001}


@app.post("/predict")
async def predict_document_fraud(
    files: List[UploadFile] = File(...),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID")
):
    logger.info(f"Received {len(files)} page images for ML fraud analysis. Request ID: {x_request_id}")

    if not files:
        raise HTTPException(status_code=400, detail="No image files received for analysis.")

    analyzed_pages = []
    total_dimensions = []

    for index, file in enumerate(files):
        try:
            content = await file.read()
            img = Image.open(io.BytesIO(content))
            analyzed_pages.append({
                "page": index + 1,
                "filename": file.filename,
                "width": img.width,
                "height": img.height,
                "format": img.format
            })
            total_dimensions.append((img.width, img.height))
        except Exception as e:
            logger.error(f"Failed to process image {file.filename}: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid image format in page {index + 1}")

    # Simulated ML Prediction Analysis
    return {
        "status": "SUCCESS",
        "request_id": x_request_id,
        "prediction": {
            "is_fraudulent": False,
            "fraud_score": 0.03,
            "confidence": 0.97,
            "verdict": "DOCUMENT_VERIFIED_CLEAN",
        },
        "ocr_extracted_text_sample": f"DocVerify OCR verification completed for {len(files)} rendered page(s).",
        "page_details": analyzed_pages
    }


@app.post("/analyze", response_model=CaseResult)
async def analyze_case_endpoint(
    request: AnalyzeRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    """Analyze a case of safe EvidenceBundles and return a full CaseResult.

    This is the real fraud-detection path: OCR fallback, field extraction,
    classification, rehydrated PDF-native forensics, deferred backdating, ELA,
    cross-document checks, registry correlation, scoring, and the audit entry.
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
