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
    list_folder,
    path_parts,
    save_upload,
    shared_file,
    shared_folder,
    valid_name,
)
from src.services.file_transfer.page import folder_url, format_size, index_page
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
        root = self.server.folder
        url = urlsplit(self.path)
        path = unquote(url.path)
        # Folder pages end in "/"; anything else is a file.
        if path.endswith("/"):
            self._serve_folder(path, url.query, include_body)
            return
        if path.strip("/") and shared_folder(root, path) is not None:
            # A folder typed without its trailing slash: go to its page.
            self.send_response(301)
            self.send_header("Location", folder_url(path_parts(path) or []))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if not self.server.access.unlocked(self._session_token()):
            # The code is required: the list is view-only until it is entered.
            self.send_error(401, "Enter the code on the File Transfer page first.")
            return
        file = shared_file(root, path)
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

    def _serve_folder(self, path: str, query: str, include_body: bool) -> None:
        folder = shared_folder(self.server.folder, path)
        if folder is None:
            self.send_error(404)
            return
        access = self.server.access
        folders, files = list_folder(folder)
        body = index_page(
            folders,
            files,
            current=path_parts(path),
            uploads_enabled=access.uploads_enabled,
            code_required=access.code_required,
            unlocked=access.unlocked(self._session_token()),
            wrong_code="wrong" in parse_qs(query, keep_blank_values=True),
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _unlock(self) -> None:
        length = self._content_length()
        if length is None or length > 1024:
            self._reject(400, "Send the code.")
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        token = self.server.access.unlock(form.get("code", [""])[0])
        if token is None:
            # Slow down guessing.
            time.sleep(1)
            self.log_message("wrong code")
        # Return to the folder the code was entered in, if it still exists.
        back = form.get("next", [""])[0]
        page = folder_url(path_parts(back)) if shared_folder(self.server.folder, back) else "/"
        self.send_response(303)
        self.send_header("Location", page if token else page + "?wrong")
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
        query = parse_qs(urlsplit(self.path).query)
        name = query.get("name", [""])[0]
        if not valid_name(name):
            self._reject(400, "That file name cannot be used.")
            return
        # Uploads go into an existing folder; only the host creates folders.
        target = shared_folder(self.server.folder, query.get("folder", [""])[0])
        if target is None:
            self._reject(404, "That folder doesn't exist on the sharing Mac.")
            return
        length = self._content_length()
        if length is None:
            self._reject(411, "The upload size is missing.")
            return
        if length > self.server.max_upload_bytes:
            limit = format_size(self.server.max_upload_bytes)
            self._reject(413, f"Files can be up to {limit}.")
            return
        if shutil.disk_usage(target).free < length + MIN_FREE_BYTES:
            self._reject(507, "The sharing Mac does not have enough free space.")
            return
        try:
            saved = save_upload(target, name, self.rfile, length)
        except (ConnectionError, TimeoutError):
            self.close_connection = True
            return
        except OSError:
            self._reject(500, "The file could not be saved.")
            return
        where = target.relative_to(self.server.folder) / saved
        self.log_message("uploaded %s (%d bytes)", where, length)
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
