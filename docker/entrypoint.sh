#!/bin/sh
# OpenYuGi container entrypoint (mount the SMB share ROOT).
#
# The share root is mounted at /app/nas. The app hardcodes several data paths
# relative to /app (e.g. data/collections, data/images), so we give it a
# dedicated subfolder on the share and expose it at /app/data via a symlink:
#
#   /app/data  ->  /app/nas/<OPENYUGI_DATA_SUBDIR>
#
# This avoids depending on a pre-created share subdirectory: the app's own
# os.makedirs calls populate it inside the already-writable mounted root.
set -e

NAS_ROOT="${OPENYUGI_NAS_ROOT:-/app/nas}"
SUBDIR="${OPENYUGI_DATA_SUBDIR:-openyugi}"
DATA_TARGET="${NAS_ROOT}/${SUBDIR}"
DATA_LINK="/app/data"

# Create the dedicated data directory inside the mounted share root.
mkdir -p "${DATA_TARGET}"

# Point /app/data at it. Replace any stale file/dir/link from a prior layout.
if [ -L "${DATA_LINK}" ]; then
    rm -f "${DATA_LINK}"
elif [ -e "${DATA_LINK}" ]; then
    # A real (empty) dir baked into the image — remove so we can symlink.
    rmdir "${DATA_LINK}" 2>/dev/null || rm -rf "${DATA_LINK}"
fi
ln -sfn "${DATA_TARGET}" "${DATA_LINK}"

echo "OpenYuGi: /app/data -> ${DATA_TARGET}"
exec "$@"
