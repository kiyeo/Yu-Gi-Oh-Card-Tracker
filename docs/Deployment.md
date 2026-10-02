# Deployment (Docker)

OpenYuGi ships with a Docker setup intended for self-hosting — for example on a
Raspberry Pi 5 behind a reverse proxy, with collection data persisted on a NAS.
Two Compose files are provided:

| File | Use |
| --- | --- |
| `docker-compose.standalone.yml` | Fully self-contained. Stores all runtime data in a local Docker-managed volume. No external share, no credentials. |
| `docker-compose.yaml` | NAS-backed. Persists the data directory on an SMB/CIFS share. Intended to be composed from a homelab repo alongside a reverse proxy. |

Both build the same `openyugi` image from the `Dockerfile`.

## The image

The `Dockerfile` is a **multi-stage, CPU-only** build:

- **CPU-only PyTorch.** `torch`/`torchvision` are installed first from the PyTorch
  CPU index (`https://download.pytorch.org/whl/cpu`) so the ~6 GB CUDA build is
  never pulled transitively by `easyocr` / `ultralytics` / `python-doctr`. This
  keeps the image around **3.4 GB** instead of ~11.5 GB and suits CPU-only
  devices such as the Pi 5.
- **Multi-stage.** A builder stage holds `build-essential` and compiles wheels
  into a virtualenv; the runtime stage copies only the finished venv, so the
  compiler toolchain and pip caches never reach the final image. The runtime
  stage installs just the shared libraries the CV/OCR stack needs at import time
  (`libgl1`, `libglib2.0-0`).
- **Baked YOLO weights.** `docker/download_weights.py` fetches the Ultralytics
  weights used by the scanner into the image at build time, so they are not
  written to the container's writable layer (important on a space-constrained
  USB boot drive) or re-downloaded on every recreate. The download is
  best-effort — a temporarily unavailable weight does not fail the build.
- **Non-root user.** The app runs as uid/gid **1000** (`openyugi`) to match the
  CIFS mount ownership, and `/app` is made writable so the app's relative
  `logs/` directory and `data/` can be created.
- **Port.** NiceGUI serves on **8084**.
- **Entrypoint.** `docker/entrypoint.sh` wires up the data directory (see below)
  and then execs `python main.py`. It is invoked via `sh` with an absolute path
  so it does not depend on the file's executable bit surviving the build.

## Standalone deployment (recommended to start)

Self-contained; everything lives in a local Docker volume (`openyugi_data`):

```bash
docker compose -f docker-compose.standalone.yml up --build -d
docker compose -f docker-compose.standalone.yml logs -f ygo-tracker
```

Then open <http://localhost:8084> and sign in with `admin` / `admin`.

Set a strong, stable `OPENYUGI_STORAGE_SECRET` (≥32 characters) in an `.env`
file next to the Compose file so logins survive restarts.

## NAS-backed deployment (CIFS/SMB)

`docker-compose.yaml` persists the data directory on an SMB share. Notable points:

- **Share root is mounted, not a subfolder.** The CIFS volume mounts the share
  **root** at `/app/nas`. The entrypoint then creates a dedicated subfolder
  (`OPENYUGI_DATA_SUBDIR`, default `openyugi`) and symlinks `/app/data` to it.
  This matters: letting the app create the folder means it inherits the share's
  mapped ownership so the container can write files into it. **Do not
  pre-create the subfolder as a different user** — a folder owned by another
  account on the NAS can block file creation even when directory creation
  succeeds.
- **Config and model caches live on the share.** `OPENYUGI_CONFIG_FILE` points
  into `/app/data`, and the EasyOCR/DocTR/Torch/HuggingFace cache dirs are
  redirected there too, keeping them off the local disk. (Trivial matplotlib
  and Ultralytics config files are kept on container-local `/tmp` instead.)
- **CIFS options.** The volume uses `uid=1000,gid=1000,noperm,nobrl,vers=3.0`.
  `noperm` defers permission checks to the SMB server (which already authorized
  the user); `nobrl` avoids byte-range locks some servers reject.
- **Ports are commented out** because this file is intended to run behind a
  reverse proxy. If you expose it directly, uncomment the `ports:` mapping.

Provide `USERNAME` (and a password/credentials as your share requires) and
`OPENYUGI_STORAGE_SECRET` via an `.env` file. Note that `docker-compose.yaml`
uses `build: ./Yu-Gi-Oh-Card-Tracker`, i.e. it expects to be composed from a
parent (homelab) directory with this repository checked out as a subfolder;
adjust the `build:` path if you run it from the repository root.

### Reverse proxy and WebSockets

NiceGUI relies on a persistent WebSocket connection. If you place OpenYuGi
behind nginx (or similar), the proxy **must** forward the WebSocket upgrade or
the UI will load but you will not be able to sign in:

```nginx
location / {
    proxy_pass http://<host>:8084;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

When serving exclusively over HTTPS, also set `OPENYUGI_SECURE_COOKIES=1`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `OPENYUGI_STORAGE_SECRET` | Stable session-signing secret (≥32 chars). Set this so logins survive restarts. |
| `OPENYUGI_SECURE_COOKIES` | `1`/`true`/`yes` when served exclusively over HTTPS. |
| `OPENYUGI_CONFIG_FILE` | Absolute path for `config.json` (points into the persisted data dir in Docker). |
| `OPENYUGI_DATA_SUBDIR` | Subfolder created on the mounted share root for this app's data (NAS compose). |
| `USERNAME` | SMB username for the CIFS volume (NAS compose). |

## Troubleshooting

- **`PermissionError` writing to `/app/data`** on the NAS deployment: the share
  folder is owned by a different account than the container's mapped user. Let
  the entrypoint create the subfolder (don't pre-create it), or `chown` it on
  the NAS to the account your SMB user maps to.
- **UI loads but login fails** behind a proxy: enable WebSocket upgrade (see
  above).
- **Image build fails with `no space left on device`**: prune old build layers
  (`docker builder prune -af`) — the torch/OCR layers are large.
