"""Which files in the shared folder may be listed, served, or written."""

import itertools
import os
import secrets
from pathlib import Path
from typing import BinaryIO


def list_shared_files(folder: Path) -> list[dict[str, int | str]]:
    """Visible regular files directly inside the folder, sorted by name."""

    if not folder.is_dir():
        return []
    files = []
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.name.startswith(".") or not entry.is_file(follow_symlinks=False):
                continue
            files.append(
                {"name": entry.name, "size": entry.stat(follow_symlinks=False).st_size}
            )
    return sorted(files, key=lambda file: str(file["name"]).lower())


def valid_name(name: str) -> bool:
    """A visible file name directly inside the folder: no paths or hidden files."""

    return (
        bool(name)
        and not name.startswith(".")
        and not any(c in name for c in "/\\")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
        and len(name.encode("utf-8")) <= 255
    )


def shared_file(folder: Path, name: str) -> Path | None:
    """Resolve a requested name, refusing anything outside the shared folder.

    Only plain files directly inside the folder are served: no subfolders,
    hidden files, or symlinks that could point elsewhere on this computer.
    """

    if not valid_name(name):
        return None
    path = folder / name
    if path.is_symlink() or not path.is_file():
        return None
    return path


def save_upload(folder: Path, name: str, body: BinaryIO, length: int) -> str:
    """Store an upload under a free name and return the name it was saved as.

    The body goes to a hidden temporary file first, so a half-finished upload
    is never listed or downloaded, and an existing file is never replaced:
    a clash is saved as "name (1).ext".
    """

    temporary = folder / f".upload-{secrets.token_hex(8)}.part"
    try:
        with temporary.open("xb") as output:
            remaining = length
            while remaining:
                chunk = body.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ConnectionError("The upload was interrupted.")
                output.write(chunk)
                remaining -= len(chunk)
        stem, suffix = os.path.splitext(name)
        for attempt in itertools.count():
            candidate = name if attempt == 0 else f"{stem} ({attempt}){suffix}"
            try:
                # A hard link fails rather than overwrite, even if two
                # uploads pick the same name at the same moment.
                os.link(temporary, folder / candidate)
                return candidate
            except FileExistsError:
                continue
    finally:
        temporary.unlink(missing_ok=True)
    raise AssertionError("unreachable")
