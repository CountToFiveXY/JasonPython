from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from io import BytesIO
from pathlib import Path
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from PIL import Image, ImageDraw, ImageFont


router = APIRouter(prefix="/v1/ranking", tags=["Images"])

WIDTH = 304
HEIGHT = 506
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "unite_galaxy_logo.png"


class CardType(str, Enum):
    SE = "SE"
    SP = "SP"
    CH = "CH"


PERCENTAGES: dict[CardType, tuple[int, ...]] = {
    CardType.CH: (1, 5, 25, 50, 75, 100),
    CardType.SP: (1, 10, 25, 50, 75, 100),
    CardType.SE: (5, 10, 25, 50, 75, 100),
}


class RankingRequest(BaseModel):
    total: int = Field(gt=0, description="Total number of participants")
    type: CardType
    car: str = Field(min_length=1, max_length=16)

    @field_validator("car")
    @classmethod
    def normalize_car(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("car must not be blank")
        return value


def _font(size: int, *, bold: bool = False, condensed: bool = False):
    del condensed  # Retained in the signature for the existing layout calls.
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def ranking_count(total: int, percentage: int) -> int:
    value = Decimal(total) * Decimal(percentage) / Decimal(100)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _centered_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1]), text, font=font, fill=fill)


def _row_text(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    top: int,
    height: int,
    text: str,
    font,
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    glyph_height = box[3] - box[1]
    y = top + (height - glyph_height) / 2 - box[1]
    draw.text((x, y), text, font=font, fill="black")


def _draw_logo(image: Image.Image) -> None:
    with Image.open(LOGO_PATH) as source:
        logo = source.convert("RGBA")
        logo.thumbnail((104, 104), Image.Resampling.LANCZOS)
        image.paste(logo, (23, 0), logo)


def save_to_desktop(
    image_bytes: bytes,
    request: RankingRequest,
    generated_at: datetime,
) -> Path:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    safe_car = re.sub(r"[^A-Za-z0-9_-]+", "-", request.car).strip("-") or "car"
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_path = desktop / f"{safe_car}_{request.type.value}_{timestamp}.png"
    output_path.write_bytes(image_bytes)
    return output_path


def render_ranking(
    request: RankingRequest,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), "#3b3b3b")
    draw = ImageDraw.Draw(image)
    _draw_logo(image)

    car_font = _font(38, bold=True, condensed=True)
    car_text = request.car.upper()
    while draw.textbbox((0, 0), car_text, font=car_font)[2] > 92 and car_font.size > 18:
        car_font = _font(car_font.size - 1, bold=True, condensed=True)
    _centered_text(draw, (229, 29), car_text, car_font, "white")

    row_top = 105
    row_height = 54
    regular_font = _font(34, condensed=True)
    bold_font = _font(32, bold=True, condensed=True)
    for index, percentage in enumerate(PERCENTAGES[request.type]):
        top = row_top + index * row_height
        if percentage == 100:
            fill = "#f9e4fa"
            font = bold_font
        else:
            fill = "#ffffff" if index % 2 == 0 else "#eeeeee"
            font = regular_font
        draw.rectangle((0, top, WIDTH, top + row_height - 1), fill=fill)
        _row_text(
            draw,
            x=8,
            top=top,
            height=row_height,
            text=f"{percentage}%",
            font=font,
        )
        _row_text(
            draw,
            x=159,
            top=top,
            height=row_height,
            text=str(ranking_count(request.total, percentage)),
            font=font,
        )

    draw.rectangle((0, 424, WIDTH, 429), fill="black")

    timestamp = generated_at or datetime.now().astimezone()
    timestamp_text = f"{timestamp.year}/{timestamp.month}/{timestamp.day} {timestamp.hour}:{timestamp:%M}"
    timestamp_font = _font(27, bold=True, condensed=True)
    _centered_text(draw, (152, 450), timestamp_text, timestamp_font, "white")

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


@router.post("", response_class=StreamingResponse)
def create_ranking(request: RankingRequest) -> StreamingResponse:
    generated_at = datetime.now().astimezone()
    image_bytes = render_ranking(request, generated_at=generated_at)
    output_path = save_to_desktop(image_bytes, request, generated_at)
    return StreamingResponse(
        BytesIO(image_bytes),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{output_path.name}"'
        },
    )
