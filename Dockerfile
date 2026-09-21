# OpenYuGi - NiceGUI web app
# Python 3.11 matches the packaged-build workflow.
FROM python:3.11-slim

# System libraries required by the CV/OCR stack (OpenCV, EasyOCR, DocTR, Torch).
# The project uses opencv-python-headless, so no full GUI GL stack is needed,
# but libGL and glib shared objects are still loaded at import time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Keep Python output unbuffered and skip .pyc files inside the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Pre-download the YOLO/Ultralytics weights used by the scanner INTO the image.
# Ultralytics resolves bare model names (e.g. 'yolov8l.pt') against the current
# working directory and, if missing, downloads them there at runtime. On the
# Pi 5 that writable layer lives on the space-constrained USB OS drive and would
# re-download on every container recreate. Baking them in makes it a one-time,
# fixed cost and lets the scanner run offline.
# (EasyOCR/DocTR/Torch caches are instead redirected to the NAS volume via env
#  vars in docker-compose.yml, since those libraries honor cache-dir env vars.)
RUN set -eux; \
    for w in yolov8l.pt yolov8n-obb.pt yolo26l-obb.pt yolo26l-cls.pt yolo26n-cls.pt; do \
        python - "$w" <<'PY' || echo "skip: $w (not fetched at build time)"; \
import sys, urllib.request
name = sys.argv[1]
# Ultralytics assets are served from the GitHub releases CDN.
url = f"https://github.com/ultralytics/assets/releases/latest/download/{name}"
try:
    urllib.request.urlretrieve(url, name)
    print(f"fetched {name}")
except Exception as e:
    print(f"could not fetch {name}: {e}")
    raise
PY
    done; \
    ls -la /app/*.pt || true

# NiceGUI serves on 0.0.0.0:8080 by default.
EXPOSE 8080

# Run from the repository root so relative data paths (data/, config.json) resolve.
CMD ["python", "main.py"]
