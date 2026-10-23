"""LAN file server for the local FileTransfer folder.

Devices can always download. Uploading is off unless the host turns it on,
and then each device must first enter the upload code shown on the host Mac.
"""

import hmac
import html
import itertools
import json
import mimetypes
import os
import secrets
import selectors
import shutil
import socket
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from typing import BinaryIO
from urllib.parse import parse_qs, quote, unquote, urlsplit

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


class HostNameInUseError(RuntimeError):
    """Another device on the network is already sharing under the name."""

    def __init__(self, host_name: str, owner: str | None) -> None:
        self.host_name = host_name
        self.owner = owner
        where = f" from {owner}" if owner else " from another device"
        super().__init__(
            f"{host_name} is already being shared{where}. Stop sharing there first."
        )


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


def lan_address() -> str | None:
    """The IPv4 address other devices on the LAN use to reach this computer.

    Prefers the Wi-Fi or Ethernet interface (en*, bridge*) so a VPN tunnel,
    which other devices cannot reach, is never chosen.
    """

    for _, name in sorted(socket.if_nameindex(), key=lambda interface: interface[1]):
        if not name.startswith(("en", "bridge")):
            continue
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", name],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            break
        address = result.stdout.strip()
        # 169.254.x.x is a self-assigned address with no working network.
        if address and not address.startswith("169.254."):
            return address
    return _default_route_address()


def _default_route_address() -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            # Connecting a UDP socket only picks the outgoing interface;
            # no packet is sent.
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith(("127.", "0.")) else address


class UploadAccess:
    """Whether uploads are on, and the code devices enter to unlock them.

    A device that enters the code gets a cookie holding a random session
    token, so it is asked only once per sharing session. Turning uploads
    off and on again issues a new code and signs every device out.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.code = ""
        self.token = ""
        self._failures = 0

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if enabled and not self.enabled:
                self.code = _new_code()
                self.token = secrets.token_urlsafe(32)
                self._failures = 0
            elif not enabled:
                self.code = self.token = ""
            self.enabled = enabled

    def unlock(self, code: str) -> str | None:
        """The session token for a correct code; None otherwise."""

        with self._lock:
            if not self.enabled:
                return None
            if hmac.compare_digest(code.strip(), self.code):
                self._failures = 0
                return self.token
            self._failures += 1
            if self._failures >= MAX_CODE_FAILURES:
                # Too many guesses: replace the code the host shows.
                self.code = _new_code()
                self._failures = 0
            return None

    def allows(self, token: str | None) -> bool:
        with self._lock:
            return self.enabled and bool(token) and hmac.compare_digest(token, self.token)


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


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


_PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JasonApp File Transfer</title>
<style>
body { font: 16px -apple-system, system-ui, sans-serif; margin: 0 auto; max-width: 720px; padding: 16px; }
ul { list-style: none; padding: 0; }
li { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid #8884; }
a { overflow-wrap: anywhere; }
span { color: #888; white-space: nowrap; }
section { padding: 12px; border: 1px solid #8886; border-radius: 10px; }
input, button { font: inherit; }
progress { width: 100%; }
.error { color: #d33; }
</style>
</head>
<body>
<h1>File Transfer</h1>
$upload
<ul>$rows</ul>
</body>
</html>""")

_CODE_FORM = """<section>
<form method="post" action="/unlock">
<label>Upload code <input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required></label>
<button>Unlock uploads</button>
</form>
$message
</section>"""

_UPLOAD_FORM = """<section>
<form id="upload">
<input type="file" id="files" multiple required>
<button>Upload</button>
</form>
<progress id="progress" value="0" max="1" hidden></progress>
<p id="status"></p>
</section>
<script>
const form = document.getElementById("upload");
const progress = document.getElementById("progress");
const status = document.getElementById("status");
function send(file) {
  return new Promise(function (resolve, reject) {
    const request = new XMLHttpRequest();
    request.open("POST", "/upload?name=" + encodeURIComponent(file.name));
    request.upload.onprogress = function (event) {
      if (event.lengthComputable) progress.value = event.loaded / event.total;
    };
    request.onload = function () {
      if (request.status === 201) return resolve();
      if (request.status === 401) location.reload();
      let message = "Upload failed.";
      try { message = JSON.parse(request.responseText).error; } catch (error) {}
      reject(new Error(message));
    };
    request.onerror = function () { reject(new Error("Upload failed. Check the connection.")); };
    request.send(file);
  });
}
form.onsubmit = async function (event) {
  event.preventDefault();
  const files = Array.from(document.getElementById("files").files);
  progress.hidden = false;
  try {
    for (let index = 0; index < files.length; index++) {
      status.textContent = "Uploading " + (index + 1) + " of " + files.length + ": " + files[index].name;
      progress.value = 0;
      await send(files[index]);
    }
    location.reload();
  } catch (error) {
    progress.hidden = true;
    status.className = "error";
    status.textContent = error.message;
  }
};
</script>"""


def _index_page(
    files: list[dict[str, int | str]],
    uploads_enabled: bool = False,
    unlocked: bool = False,
    wrong_code: bool = False,
) -> str:
    rows = "".join(
        f'<li><a href="/{quote(str(file["name"]))}" download>'
        f'{html.escape(str(file["name"]))}</a>'
        f'<span>{_format_size(int(file["size"]))}</span></li>'
        for file in files
    ) or "<li>No files are shared yet.</li>"
    if not uploads_enabled:
        upload = ""
    elif unlocked:
        upload = _UPLOAD_FORM
    else:
        message = '<p class="error">That code is not right. Check the code on the sharing Mac.</p>'
        upload = Template(_CODE_FORM).substitute(message=message if wrong_code else "")
    return _PAGE.substitute(rows=rows, upload=upload)


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class _TransferServer(ThreadingHTTPServer):
    daemon_threads = True
    folder: Path
    uploads: UploadAccess

    def handle_error(self, request, client_address) -> None:  # type: ignore[override]
        # A device closing the page mid-transfer is routine, not an error.
        pass


class _TransferHandler(BaseHTTPRequestHandler):
    server: _TransferServer
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
            uploads = self.server.uploads
            body = _index_page(
                list_shared_files(folder),
                uploads_enabled=uploads.enabled,
                unlocked=uploads.allows(self._upload_token()),
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
        token = self.server.uploads.unlock(form.get("code", [""])[0])
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
        uploads = self.server.uploads
        if not uploads.enabled:
            self._reject(403, "Uploads are turned off on the sharing Mac.")
            return
        if not uploads.allows(self._upload_token()):
            self._reject(401, "Enter the upload code first.")
            return
        name = parse_qs(urlsplit(self.path).query).get("name", [""])[0]
        if not valid_name(name):
            self._reject(400, "That file name cannot be used.")
            return
        length = self._content_length()
        if length is None:
            self._reject(411, "The upload size is missing.")
            return
        if length > MAX_UPLOAD_BYTES:
            limit = _format_size(MAX_UPLOAD_BYTES)
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

    def _upload_token(self) -> str | None:
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


# Runs dns-sd and kills it once the pipe from this process closes, which
# also happens if the API crashes or is force-quit. Without it an orphaned
# dns-sd would keep claiming the name and lock out every other Mac.
_TIED_TO_PARENT = (
    'exec 3<&0; dns-sd "$@" </dev/null & child=$!; '
    '{ read -r _ <&3; kill "$child" 2>/dev/null; } & '
    'wait "$child"'
)


class BonjourAnnouncer:
    """Announces a .local name for this Mac through macOS's own Bonjour service.

    Bonjour lets only one device own a name, so a second Mac that tries to
    share is refused instead of silently taking over the address.
    """

    def __init__(self, host_name: str = FILE_TRANSFER_HOST_NAME, timeout: float = 5) -> None:
        self.host_name = host_name
        self._timeout = timeout
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def is_active(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def claim(self, address: str, port: int) -> bool:
        """Announce the name; False when Bonjour is unavailable on this system."""

        self.release()
        if shutil.which("dns-sd") is None:
            return False
        try:
            process = subprocess.Popen(
                [
                    "/bin/sh", "-c", _TIED_TO_PARENT, "dns-sd",
                    "-P", "JasonApp Files", "_http._tcp", "local",
                    str(port), self.host_name, address,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError:
            return False
        assert process.stdout is not None
        record = f"record {self.host_name}:"
        output = ""
        in_use = False
        deadline = time.monotonic() + self._timeout
        with selectors.DefaultSelector() as selector:
            # Read the raw pipe: a buffered readline() can hold the reply in
            # Python's buffer while select() waits for data that already came.
            selector.register(process.stdout, selectors.EVENT_READ)
            while (remaining := deadline - time.monotonic()) > 0:
                if not selector.select(remaining):
                    continue
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                output += chunk.decode("utf-8", "replace")
                replies = [line for line in output.splitlines() if record in line]
                if any("Name now registered" in line for line in replies):
                    self._process = process
                    # Keep draining output so dns-sd never blocks on a full pipe.
                    threading.Thread(
                        target=process.stdout.read,
                        name="file-transfer-bonjour",
                        daemon=True,
                    ).start()
                    return True
                if any("Name in use" in line for line in replies):
                    in_use = True
                    break
        self._end(process)
        if in_use:
            raise HostNameInUseError(self.host_name, self._current_owner())
        # Bonjour did not answer in time; devices can still use the IP address.
        return False

    def release(self) -> None:
        process, self._process = self._process, None
        if process is not None:
            self._end(process)

    @staticmethod
    def _end(process: subprocess.Popen[bytes]) -> None:
        """Withdraw the name: closing the pipe makes the wrapper stop dns-sd."""

        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # The wrapper and dns-sd share a session of their own.
            try:
                os.killpg(process.pid, 9)
            except ProcessLookupError:
                pass
            process.wait()

    def _current_owner(self) -> str | None:
        try:
            return socket.gethostbyname(self.host_name)
        except OSError:
            return None


class FileTransferService:
    """Starts and stops one transfer server shared by every API request."""

    def __init__(
        self,
        folder: Path = FILE_TRANSFER_DIR,
        port: int = FILE_TRANSFER_PORT,
        host: str = "0.0.0.0",
        announcer: BonjourAnnouncer | None = None,
    ) -> None:
        self.folder = folder
        self._preferred_port = port
        self._host = host
        self._announcer = announcer or BonjourAnnouncer()
        self._uploads = UploadAccess()
        self._server: _TransferServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, allow_uploads: bool = False) -> dict:
        """Start sharing, or change whether uploads are allowed while sharing."""

        with self._lock:
            self._uploads.set_enabled(allow_uploads)
            if self._server is None:
                self.folder.mkdir(parents=True, exist_ok=True)
                try:
                    server = _TransferServer((self._host, self._preferred_port), _TransferHandler)
                except OSError:
                    # The preferred port is taken; let the system pick a free one.
                    server = _TransferServer((self._host, 0), _TransferHandler)
                server.folder = self.folder
                server.uploads = self._uploads
                address = lan_address()
                if address is not None:
                    try:
                        self._announcer.claim(address, server.server_address[1])
                    except HostNameInUseError:
                        server.server_close()
                        self._uploads.set_enabled(False)
                        raise
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
            self._announcer.release()
            self._uploads.set_enabled(False)
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
        ip_url = _url(address, port) if address and port else None
        host_name = self._announcer.host_name if port and self._announcer.is_active else None
        return {
            "running": server is not None,
            "folder": str(self.folder),
            "port": port,
            "host_name": host_name,
            "url": _url(host_name, port) if host_name and port else ip_url,
            "ip_url": ip_url,
            "allow_uploads": self._uploads.enabled,
            "upload_code": self._uploads.code or None,
            "files": list_shared_files(self.folder),
        }


def _url(host: str, port: int) -> str:
    return f"http://{host}" if port == 80 else f"http://{host}:{port}"
