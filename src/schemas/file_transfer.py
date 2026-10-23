"""HTTP schemas for the LAN file transfer server."""

from pydantic import BaseModel


class SharedFile(BaseModel):
    name: str
    size: int


class FileTransferStatus(BaseModel):
    running: bool
    folder: str
    port: int | None
    url: str | None
    files: list[SharedFile]
