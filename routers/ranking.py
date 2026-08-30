from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from PIL import Image, ImageDraw, ImageFont


router = APIRouter(prefix="/v1/ranking", tags=["Images"])

WIDTH = 304
HEIGHT = 506
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "unite_galaxy_logo.png"
CAR_TEXT_MAX_WIDTH = 92
CAR_TEXT_MAX_HEIGHT = 48


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


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3400" <= character <= "\u4dbf"
        or "\u4e00" <= character <= "\u9fff"
        or "\uf900" <= character <= "\ufaff"
        for character in text
    )


def _font(
    size: int,
    *,
    bold: bool = False,
    condensed: bool = False,
    text: str = "",
):
    del condensed  # Retained in the signature for the existing layout calls.
    candidates = []
    if _contains_cjk(text):
        candidates.extend(
            [
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
                if bold
                else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
            ]
        )
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


def _fitted_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    maximum_size: int,
    maximum_width: int,
    maximum_height: int,
    bold: bool = False,
    condensed: bool = False,
):
    for size in range(maximum_size, 7, -1):
        font = _font(size, bold=bold, condensed=condensed, text=text)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= maximum_width and box[3] - box[1] <= maximum_height:
            return font
    return _font(8, bold=bold, condensed=condensed, text=text)


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


def render_ranking(
    request: RankingRequest,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), "#3b3b3b")
    draw = ImageDraw.Draw(image)
    _draw_logo(image)

    car_text = request.car.upper()
    car_font = _fitted_font(
        draw,
        car_text,
        maximum_size=38,
        maximum_width=CAR_TEXT_MAX_WIDTH,
        maximum_height=CAR_TEXT_MAX_HEIGHT,
        bold=True,
        condensed=True,
    )
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
    return StreamingResponse(
        BytesIO(image_bytes),
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="ranking.png"'},
    )
