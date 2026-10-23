"""Controls for the download-only LAN file transfer server."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from src.dependencies import get_file_transfer_service
from src.schemas import FileTransferStatus
from src.services import FileTransferService


LOCAL_CLIENTS = {"127.0.0.1", "::1"}


def require_local_client(request: Request) -> None:
    """The API listens on every interface; only this computer may share files."""

    if request.client is None or request.client.host not in LOCAL_CLIENTS:
        raise HTTPException(
            status_code=403,
            detail="File transfer can only be controlled from this computer.",
        )


router = APIRouter(
    prefix="/v1/file-transfer",
    tags=["File Transfer"],
    dependencies=[Depends(require_local_client)],
)


@router.get("", response_model=FileTransferStatus)
async def file_transfer_status(
    service: FileTransferService = Depends(get_file_transfer_service),
) -> FileTransferStatus:
    return FileTransferStatus(**await run_in_threadpool(service.status))


@router.post("/start", response_model=FileTransferStatus)
async def start_file_transfer(
    service: FileTransferService = Depends(get_file_transfer_service),
) -> FileTransferStatus:
    try:
        status = await run_in_threadpool(service.start)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not start file transfer: {exc.strerror or exc}",
        ) from exc
    return FileTransferStatus(**status)


@router.post("/stop", response_model=FileTransferStatus)
async def stop_file_transfer(
    service: FileTransferService = Depends(get_file_transfer_service),
) -> FileTransferStatus:
    return FileTransferStatus(**await run_in_threadpool(service.stop))
