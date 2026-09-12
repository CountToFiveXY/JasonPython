"""Static image use case."""

from pathlib import Path


IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "metroidzm_map.jpg"


class ImageService:
    def get_display_image(self) -> Path:
        return IMAGE_PATH
