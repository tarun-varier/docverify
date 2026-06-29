import hashlib
import json
import logging
import os
import sys
from typing import Any, Dict

def resolve_ml_service_url() -> str:
    configured_url = os.getenv("ML_SERVICE_URL")
    if configured_url:
        return configured_url

    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in {"1", "true", "yes"}:
        return "http://model:8001/predict"

    return "http://127.0.0.1:8001/predict"


# Environment Variable Configurations
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_MB * 1024 * 1024)
ML_SERVICE_URL = resolve_ml_service_url()
ALLOWED_MIME_TYPES = os.getenv("ALLOWED_MIME_TYPES", "application/pdf").split(",")

# Configure Structured JSON Logging
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_data["request_id"] = getattr(record, "request_id")
        if hasattr(record, "extra_data"):
            log_data.update(getattr(record, "extra_data"))
        return json.dumps(log_data)


logger = logging.getLogger("security_gateway")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)


def get_logger() -> logging.Logger:
    return logger


def calculate_sha256(file_path: str) -> str:
    """Calculate SHA-256 hash of a file for audit trails."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def validate_pdf_header(file_path: str) -> bool:
    """Verify that the file starts with the standard PDF magic bytes (%PDF-)."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF-")
    except Exception:
        return False
