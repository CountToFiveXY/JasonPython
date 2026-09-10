from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(prefix="/display", tags=["Images"])
IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "metroidzm_map.jpg"


@router.get("")
def get_image() -> FileResponse:
    return FileResponse(IMAGE_PATH, media_type="image/jpeg")
