"""Small JPEG previews of shared images, made by macOS's sips and cached.

A page of photos then loads a few kilobytes per image instead of the full
files, and iPhone HEIC photos show on phones that cannot display HEIC.
"""

import hashlib
import os
import secrets
import subprocess
import threading
from pathlib import Path

IMAGE_SUFFIXES = {
    ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp",
}
# The longest side of a preview, in pixels; the page shows them at 44 px,
# so this stays sharp on high-density phone screens.
THUMBNAIL_SIZE = 200
# A page of photos asks for many previews at once; make a few at a time.
_making = threading.BoundedSemaphore(2)


def is_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_SUFFIXES


def thumbnail(source: Path, cache: Path) -> Path | None:
    """A cached JPEG preview of an image, made on first request.

    The cache name comes from the file's path, size and modification time,
    so an edited or replaced photo gets a fresh preview. None when the file
    is not an image sips can read.
    """

    stat = source.stat()
    key = hashlib.sha256(
        f"{source.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode()
    ).hexdigest()
    target = cache / f"{key}.jpg"
    if target.exists():
        return target
    with _making:
        # Another request may have made it while this one waited.
        if target.exists():
            return target
        cache.mkdir(parents=True, exist_ok=True)
        temporary = cache / f".{key}-{secrets.token_hex(4)}.jpg"
        try:
            result = subprocess.run(
                [
                    "sips", "-s", "format", "jpeg", "-s", "formatOptions", "70",
                    "-Z", str(THUMBNAIL_SIZE), str(source), "--out", str(temporary),
                ],
                capture_output=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is None or result.returncode != 0 or not temporary.exists():
            temporary.unlink(missing_ok=True)
            return None
        os.replace(temporary, target)
    return target
