"""The HTTP server devices talk to: the file list, downloads, the code, uploads."""

import json
import mimetypes
import os
import shutil
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from src.services.file_transfer.config import MIN_FREE_BYTES, UPLOAD_COOKIE
from src.services.file_transfer.files import (
    list_shared_files,
    save_upload,
    shared_file,
    valid_name,
)
from src.services.file_transfer.page import format_size, index_page
from src.services.file_transfer.access import AccessControl


class TransferServer(ThreadingHTTPServer):
    daemon_threads = True
    folder: Path
    access: AccessControl
    max_upload_bytes: int

    def handle_error(self, request, client_address) -> None:  # type: ignore[override]
        # A device closing the page mid-transfer is routine, not an error.
        pass


class TransferHandler(BaseHTTPRequestHandler):
    server: TransferServer
    server_version = "JasonAppFileTransfer"
    sys_version = ""
    timeout = 60

    def do_GET(self) -> None:
        self._serve(include_body=True)

    def do_HEAD(self) -> None:
        self._serve(include_body=False)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/unlock":
            self._unlock()
        elif path == "/upload":
            self._upload()
        else:
            self._reject(404, "Not found.")

    def _serve(self, include_body: bool) -> None:
        folder = self.server.folder
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path == "/":
            access = self.server.access
            body = index_page(
                list_shared_files(folder),
                uploads_enabled=access.uploads_enabled,
                code_required=access.code_required,
                unlocked=access.unlocked(self._session_token()),
                wrong_code="wrong" in parse_qs(url.query, keep_blank_values=True),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if include_body:
                self.wfile.write(body)
            return

        if not self.server.access.unlocked(self._session_token()):
            # The code is required: the list is view-only until it is entered.
            self.send_error(401, "Enter the code on the File Transfer page first.")
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

    def _unlock(self) -> None:
        length = self._content_length()
        if length is None or length > 1024:
            self._reject(400, "Send the upload code.")
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        token = self.server.access.unlock(form.get("code", [""])[0])
        if token is None:
            # Slow down guessing; the code is also replaced after repeated misses.
            time.sleep(1)
            self.log_message("wrong upload code")
        self.send_response(303)
        self.send_header("Location", "/" if token else "/?wrong")
        if token:
            self.send_header(
                "Set-Cookie",
                f"{UPLOAD_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict",
            )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _upload(self) -> None:
        access = self.server.access
        if not access.uploads_enabled:
            self._reject(403, "Uploads are turned off on the sharing Mac.")
            return
        if not access.unlocked(self._session_token()):
            self._reject(401, "Enter the code first.")
            return
        name = parse_qs(urlsplit(self.path).query).get("name", [""])[0]
        if not valid_name(name):
            self._reject(400, "That file name cannot be used.")
            return
        length = self._content_length()
        if length is None:
            self._reject(411, "The upload size is missing.")
            return
        if length > self.server.max_upload_bytes:
            limit = format_size(self.server.max_upload_bytes)
            self._reject(413, f"Files can be up to {limit}.")
            return
        folder = self.server.folder
        if shutil.disk_usage(folder).free < length + MIN_FREE_BYTES:
            self._reject(507, "The sharing Mac does not have enough free space.")
            return
        try:
            saved = save_upload(folder, name, self.rfile, length)
        except (ConnectionError, TimeoutError):
            self.close_connection = True
            return
        except OSError:
            self._reject(500, "The file could not be saved.")
            return
        self.log_message("uploaded %s (%d bytes)", saved, length)
        self._send_json(201, {"name": saved})

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get(UPLOAD_COOKIE)
        return morsel.value if morsel else None

    def _content_length(self) -> int | None:
        try:
            length = int(self.headers["Content-Length"])
        except (TypeError, ValueError):
            return None
        return length if length >= 0 else None

    def _reject(self, status: int, message: str) -> None:
        # The body may still be arriving; close instead of reading it.
        self.close_connection = True
        self._send_json(status, {"error": message})

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
