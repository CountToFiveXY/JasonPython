"""Settings for the LAN file transfer server, read from the environment."""

import os
from pathlib import Path

FILE_TRANSFER_DIR = Path(
    os.getenv(
        "FILE_TRANSFER_DIR",
        str(Path.home() / "Documents" / "JasonApp" / "FileTransfer"),
    )
)

# Port 80 keeps the port out of the address devices type.
FILE_TRANSFER_PORT = int(os.getenv("FILE_TRANSFER_PORT", "80"))

# Whichever Mac is sharing announces this name, so every device can use
# the same address no matter which Mac hosts.
FILE_TRANSFER_HOST_NAME = os.getenv("FILE_TRANSFER_HOST_NAME", "jason.local")

MAX_UPLOAD_BYTES = int(float(os.getenv("FILE_TRANSFER_MAX_UPLOAD_GB", "10")) * 1024**3)

# Room left on the disk after an upload, so a phone cannot fill the Mac.
MIN_FREE_BYTES = 1024**3

UPLOAD_COOKIE = "jasonapp_upload"

# Wrong codes allowed before the code is replaced, which bounds guessing.
MAX_CODE_FAILURES = 10
