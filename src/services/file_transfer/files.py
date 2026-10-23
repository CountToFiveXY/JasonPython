"""Which files in the shared folder may be listed, served, or written."""

import itertools
import os
import secrets
from pathlib import Path
from typing import BinaryIO


def list_shared_files(folder: Path) -> list[dict[str, int | str]]:
    """Visible regular files directly inside the folder, sorted by name."""

    return list_folder(folder)[1]


def list_folder(folder: Path) -> tuple[list[str], list[dict[str, int | str]]]:
    """Visible subfolders and regular files directly inside a folder, by name.

    Symlinks are left out, so nothing outside the shared folder shows up.
    """

    if not folder.is_dir():
        return [], []
    folders, files = [], []
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False):
                folders.append(entry.name)
            elif entry.is_file(follow_symlinks=False):
                files.append(
                    {"name": entry.name, "size": entry.stat(follow_symlinks=False).st_size}
                )
    return (
        sorted(folders, key=str.lower),
        sorted(files, key=lambda file: str(file["name"]).lower()),
    )


def valid_name(name: str) -> bool:
    """A visible file or folder name: no paths, hidden names, or control characters."""

    return (
        bool(name)
        and not name.startswith(".")
        and not any(c in name for c in "/\\")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
        and len(name.encode("utf-8")) <= 255
    )


def path_parts(relative: str) -> list[str] | None:
    """Split a path such as "Photos/Trip" into names, or None if any is unsafe.

    Every part must be a visible, ordinary name, so "..", hidden names and
    backslashes can never reach outside the shared folder. "" is the shared
    folder itself.
    """

    relative = relative.strip("/")
    if not relative:
        return []
    parts = relative.split("/")
    return parts if all(valid_name(part) for part in parts) else None


def shared_folder(root: Path, relative: str) -> Path | None:
    """A folder inside the shared folder, or None when it is not one.

    Each step must be a real folder, not a symlink, and the result must
    still sit inside the shared folder.
    """

    parts = path_parts(relative)
    if parts is None:
        return None
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink() or not path.is_dir():
            return None
    return path if _inside(root, path) else None


def shared_file(root: Path, relative: str) -> Path | None:
    """A regular file inside the shared folder or one of its subfolders.

    Hidden files, symlinks, and anything outside the shared folder are
    refused.
    """

    parts = path_parts(relative)
    if not parts:
        return None
    folder = shared_folder(root, "/".join(parts[:-1]))
    if folder is None:
        return None
    path = folder / parts[-1]
    if path.is_symlink() or not path.is_file():
        return None
    return path if _inside(root, path) else None


def _inside(root: Path, path: Path) -> bool:
    # A last check after the per-step rules: the real path stays inside.
    return path.resolve().is_relative_to(root.resolve())


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
