"""Pre-download the YOLO/Ultralytics scanner weights at image build time.

Ultralytics resolves bare model names (e.g. 'yolov8l.pt') against the current
working directory and downloads them there at runtime if missing. Baking them
into the image keeps them off the runtime writable layer (important on the
Pi 5's space-constrained USB OS drive) and lets the scanner run offline.
"""

import sys
import urllib.request

# Weights referenced by src/services/scanner/{pipeline,manager}.py.
WEIGHTS = [
    "yolov8l.pt",
    "yolov8n-obb.pt",
    "yolo26l-obb.pt",
    "yolo26l-cls.pt",
    "yolo26n-cls.pt",
]

BASE_URL = "https://github.com/ultralytics/assets/releases/latest/download"


def main() -> int:
    failures = []
    for name in WEIGHTS:
        url = f"{BASE_URL}/{name}"
        try:
            urllib.request.urlretrieve(url, name)
            print(f"fetched {name}")
        except Exception as exc:  # noqa: BLE001 - build-time best effort
            print(f"WARNING: could not fetch {name}: {exc}")
            failures.append(name)

    # Do not fail the whole build if an optional weight is unavailable; the app
    # will fall back to downloading it at runtime if needed.
    if failures:
        print(f"NOTE: {len(failures)} weight(s) not pre-fetched: {', '.join(failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
