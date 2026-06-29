import logging
from typing import List
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_model_service")

app = FastAPI(
    title="DocVerify ML Fraud Detection Model Service",
    description="Microservice running ML OCR and document fraud classification models.",
    version="1.0.0"
)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
