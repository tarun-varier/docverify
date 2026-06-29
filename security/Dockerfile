# Layer 0 PDF Security Gateway Dockerfile
# Base Image: Official Python 3.11 slim for minimal attack surface
FROM python:3.11-slim

# Install system dependencies (poppler-utils is required by pdf2image for rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Security Hardening: Create and switch to non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose microservice port
EXPOSE 8002

# Run FastAPI app with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]

# ==============================================================================
# DOCKER SECURITY HARDENING FLAGS (EXPLANATION FOR LOCAL RUNTIME):
# ==============================================================================
# When running this container directly via docker run, use the following flags:
#
# docker run -d \
#   --name security-gateway \
#   -p 8002:8002 \
#   --memory=512m \
#   --cpus=1 \
#   --read-only \
#   --tmpfs /tmp:rw,noexec,nosuid,size=100m \
#   security-gateway:latest
#
# SECURITY FLAG EXPLANATIONS:
# 1. --network none (or isolated internal docker network):
#    Completely cuts off external internet access from the container. Ensures zero data
#    exfiltration or unauthorized external calls during untrusted PDF scanning.
#
# 2. --read-only:
#    Mounts the container's root filesystem as read-only. Prevents any malicious PDF exploit
#    from modifying application binaries, installing backdoors, or persisting files inside the container.
#
# 3. --memory=512m:
#    Caps memory utilization to 512MB. Protects the host system against Denial of Service (DoS)
#    attacks, memory bomb PDFs (e.g., recursive object expanders or zip bombs).
#
# 4. --cpus=1:
#    Limits CPU core allocation to 1 core, preventing CPU starvation attacks or infinite loops.
# ==============================================================================
