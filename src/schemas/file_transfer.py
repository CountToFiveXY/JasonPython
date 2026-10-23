"""HTTP schemas for the LAN file transfer server."""

from pydantic import BaseModel


class SharedFile(BaseModel):
    name: str
    size: int


class FileTransferStartRequest(BaseModel):
    allow_uploads: bool = False
    require_code: bool = False


class FileTransferStatus(BaseModel):
    running: bool
    folder: str
    port: int | None
    host_name: str | None
    url: str | None
    ip_url: str | None
    allow_uploads: bool
    require_code: bool
    # Only this computer can read the status, so the code never leaves it.
    access_code: str | None
    files: list[SharedFile]
