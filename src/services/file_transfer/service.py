"""Starting, stopping, and reporting on the one shared transfer server."""

import threading
from pathlib import Path

from src.infrastructure.bonjour import BonjourAnnouncer, HostNameInUseError, lan_address
from src.services.file_transfer.config import (
    FILE_TRANSFER_DIR,
    FILE_TRANSFER_HOST_NAME,
    FILE_TRANSFER_PORT,
    MAX_UPLOAD_BYTES,
)
from src.services.file_transfer.files import list_shared_files
from src.services.file_transfer.http_server import TransferHandler, TransferServer
from src.services.file_transfer.uploads import UploadAccess


class FileTransferService:
    """Starts and stops one transfer server shared by every API request."""

    def __init__(
        self,
        folder: Path = FILE_TRANSFER_DIR,
        port: int = FILE_TRANSFER_PORT,
        host: str = "0.0.0.0",
        announcer: BonjourAnnouncer | None = None,
        max_upload_bytes: int = MAX_UPLOAD_BYTES,
    ) -> None:
        self.folder = folder
        self._preferred_port = port
        self._host = host
        self._announcer = announcer or BonjourAnnouncer(FILE_TRANSFER_HOST_NAME)
        self._max_upload_bytes = max_upload_bytes
        self._uploads = UploadAccess()
        self._server: TransferServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, allow_uploads: bool = False) -> dict:
        """Start sharing, or change whether uploads are allowed while sharing."""

        with self._lock:
            self._uploads.set_enabled(allow_uploads)
            if self._server is None:
                self.folder.mkdir(parents=True, exist_ok=True)
                try:
                    server = TransferServer((self._host, self._preferred_port), TransferHandler)
                except OSError:
                    # The preferred port is taken; let the system pick a free one.
                    server = TransferServer((self._host, 0), TransferHandler)
                server.folder = self.folder
                server.uploads = self._uploads
                server.max_upload_bytes = self._max_upload_bytes
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
