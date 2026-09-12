"""Static image HTTP endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from src.dependencies import get_image_service
from src.services import ImageService


router = APIRouter(prefix="/display", tags=["Images"])


@router.get("")
def get_image(
    service: ImageService = Depends(get_image_service),
) -> FileResponse:
    return FileResponse(service.get_display_image(), media_type="image/jpeg")
