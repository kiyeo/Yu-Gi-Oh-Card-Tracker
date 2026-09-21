# syntax=docker/dockerfile:1

###############################################################################
# OpenYuGi - NiceGUI web app (multi-stage, CPU-only build)
#
# The scanner stack (torch via easyocr / ultralytics / python-doctr) pulls the
# CUDA build of PyTorch by default on x86, which alone is ~6 GB and is useless
# on a CPU-only device like the Pi 5. We force the CPU-only wheels and use a
# multi-stage build so compilers and caches never reach the final image.
###############################################################################

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build toolchain (needed to compile any sdist-only wheels). Stays in this stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

# Install CPU-only PyTorch FIRST from the PyTorch CPU index, so the heavy CUDA
# variant is never resolved as a transitive dependency of easyocr/doctr/ultralytics.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision

# Now install the rest. torch is already satisfied, so PyPI won't pull the
# CUDA build. --no-deps is NOT used because we want the other transitive deps.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

# Runtime shared libraries required by the CV/OCR stack at import time.
# No build-essential here — the wheels are already compiled.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Copy the ready-built virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy the application code.
COPY . .

# Pre-download the YOLO/Ultralytics weights used by the scanner INTO the image so
# they are not written to the runtime layer (the Pi 5's USB OS drive) or
# re-downloaded on every container recreate. Best-effort: the build does not fail
# if a weight is temporarily unavailable.
RUN python docker/download_weights.py && ls -la /app/*.pt || true

# NiceGUI serves on 0.0.0.0:8080 by default.
EXPOSE 8080

# Run from the repository root so relative data paths (data/, config.json) resolve.
CMD ["python", "main.py"]
