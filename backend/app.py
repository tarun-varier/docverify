import os
import shutil
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from analyzer import PDFSandboxAnalyzer

app = FastAPI(
    title="DocVerify API",
    description="Simple FastAPI server with Local PDF Sandbox Scanner",
    version="1.0.0"
)

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


@app.post("/api/scan")
async def scan_pdf(file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    try:
        # Create a temporary file to store the uploaded PDF
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        # Run local sandbox scanner
        analyzer = PDFSandboxAnalyzer(tmp_path)
        report = analyzer.scan()
        
        # Clean up the temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return report
    except Exception as e:
        # Make sure to clean up even on error
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Local sandbox scanning failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",   # Listen on all interfaces
        port=8000,
        reload=True
    )