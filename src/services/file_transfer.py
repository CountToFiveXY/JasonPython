"""Download-only LAN file server for the local FileTransfer folder."""

import html
import mimetypes
import os
import shutil
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

FILE_TRANSFER_DIR = Path(
    os.getenv(
        "FILE_TRANSFER_DIR",
        str(Path.home() / "Documents" / "JasonApp" / "FileTransfer"),
    )
)
FILE_TRANSFER_PORT = int(os.getenv("FILE_TRANSFER_PORT", "8765"))


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


def shared_file(folder: Path, name: str) -> Path | None:
    """Resolve a requested name, refusing anything outside the shared folder.

    Only plain files directly inside the folder are served: no subfolders,
    hidden files, or symlinks that could point elsewhere on this computer.
    """

    if not name or name.startswith(".") or any(c in name for c in "/\\\0"):
        return None
    path = folder / name
    if path.is_symlink() or not path.is_file():
        return None
    return path


def lan_address() -> str | None:
    """The IPv4 address other devices on the LAN use to reach this computer."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            # Connecting a UDP socket only picks the outgoing interface;
            # no packet is sent.
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith(("127.", "0.")) else address


def _index_page(files: list[dict[str, int | str]]) -> str:
    rows = "".join(
        f'<li><a href="/{quote(str(file["name"]))}" download>'
        f'{html.escape(str(file["name"]))}</a>'
        f'<span>{_format_size(int(file["size"]))}</span></li>'
        for file in files
    ) or "<li>No files are shared yet.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JasonApp File Transfer</title>
<style>
body {{ font: 16px -apple-system, system-ui, sans-serif; margin: 0 auto; max-width: 720px; padding: 16px; }}
ul {{ list-style: none; padding: 0; }}
li {{ display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid #8884; }}
a {{ overflow-wrap: anywhere; }}
span {{ color: #888; white-space: nowrap; }}
</style>
</head>
<body>
<h1>File Transfer</h1>
<ul>{rows}</ul>
</body>
</html>"""


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class _DownloadServer(ThreadingHTTPServer):
    daemon_threads = True
    folder: Path

    def handle_error(self, request, client_address) -> None:  # type: ignore[override]
        # A device closing the page mid-download is routine, not an error.
        pass


class _DownloadHandler(BaseHTTPRequestHandler):
    server: _DownloadServer
    server_version = "JasonAppFileTransfer"
    sys_version = ""
    timeout = 60

    def do_GET(self) -> None:
        self._serve(include_body=True)

    def do_HEAD(self) -> None:
        self._serve(include_body=False)

    def _serve(self, include_body: bool) -> None:
        folder = self.server.folder
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            body = _index_page(list_shared_files(folder)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if include_body:
                self.wfile.write(body)
            return

        file = shared_file(folder, path.removeprefix("/"))
        if file is None:
            self.send_error(404)
            return
        try:
            handle = file.open("rb")
        except OSError:
            self.send_error(404)
            return
        with handle:
            content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.fstat(handle.fileno()).st_size))
            self.send_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{quote(file.name)}",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if include_body:
                shutil.copyfileobj(handle, self.wfile, 1024 * 1024)


class FileTransferService:
    """Starts and stops one download server shared by every API request."""

    def __init__(
        self,
        folder: Path = FILE_TRANSFER_DIR,
        port: int = FILE_TRANSFER_PORT,
        host: str = "0.0.0.0",
    ) -> None:
        self.folder = folder
        self._preferred_port = port
        self._host = host
        self._server: _DownloadServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> dict:
        with self._lock:
            if self._server is None:
                self.folder.mkdir(parents=True, exist_ok=True)
                try:
                    server = _DownloadServer((self._host, self._preferred_port), _DownloadHandler)
                except OSError:
                    # The preferred port is taken; let the system pick a free one.
                    server = _DownloadServer((self._host, 0), _DownloadHandler)
                server.folder = self.folder
                thread = threading.Thread(
                    target=server.serve_forever,
                    name="file-transfer",
                    daemon=True,
                )
                thread.start()
                self._server, self._thread = server, thread
        return self.status()

    def stop(self) -> dict:
        with self._lock:
            server, thread = self._server, self._thread
            self._server, self._thread = None, None
            if server is not None:
                server.shutdown()
                server.server_close()
            if thread is not None:
                thread.join(timeout=5)
        return self.status()

    def status(self) -> dict:
        server = self._server
        port = server.server_address[1] if server is not None else None
        address = lan_address() if server is not None else None
        return {
            "running": server is not None,
            "folder": str(self.folder),
            "port": port,
            "url": f"http://{address}:{port}" if address and port else None,
            "files": list_shared_files(self.folder),
        }
