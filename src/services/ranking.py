"""Ranking image generation use case."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.entity import CardType


WIDTH = 304
HEIGHT = 506
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "unite_galaxy_logo.png"
LOGO_ORIGIN = (23, 0)
LOGO_SIZE = 104
HEADER_HEIGHT = 105

# The car name fills the header to the right of the logo, rather than a narrow
# column in the middle of it.
CAR_TEXT_LEFT = LOGO_ORIGIN[0] + LOGO_SIZE + 8
CAR_TEXT_RIGHT = WIDTH - 10
CAR_TEXT_MAX_WIDTH = CAR_TEXT_RIGHT - CAR_TEXT_LEFT
CAR_TEXT_MAX_HEIGHT = 62
CAR_TEXT_CENTER = ((CAR_TEXT_LEFT + CAR_TEXT_RIGHT) // 2, HEADER_HEIGHT // 2)

PERCENTAGES: dict[CardType, tuple[int, ...]] = {
    CardType.CH: (1, 5, 25, 50, 75, 100),
    CardType.SP: (1, 10, 25, 50, 75, 100),
    CardType.SE: (5, 10, 25, 50, 75, 100),
}


@dataclass(frozen=True)
class RankingImage:
    content: bytes
    filename: str


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
    del condensed
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


def _text_in_box(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, font, fill):
    """Centre text on a point in both axes, whatever size the font ended up."""

    box = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (
            center[0] - (box[2] - box[0]) / 2 - box[0],
            center[1] - (box[3] - box[1]) / 2 - box[1],
        ),
        text,
        font=font,
        fill=fill,
    )


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
        logo.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS)
        image.paste(logo, LOGO_ORIGIN, logo)


def render_ranking(
    total: int,
    card_type: CardType,
    car: str,
    *,
    generated_at: datetime,
) -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), "#3b3b3b")
    draw = ImageDraw.Draw(image)
    _draw_logo(image)

    car_text = car.upper()
    car_font = _fitted_font(
        draw,
        car_text,
        maximum_size=52,
        maximum_width=CAR_TEXT_MAX_WIDTH,
        maximum_height=CAR_TEXT_MAX_HEIGHT,
        bold=True,
        condensed=True,
    )
    _text_in_box(draw, CAR_TEXT_CENTER, car_text, car_font, "white")

    row_top = 105
    row_height = 54
    regular_font = _font(34, condensed=True)
    bold_font = _font(32, bold=True, condensed=True)
    for index, percentage in enumerate(PERCENTAGES[card_type]):
        top = row_top + index * row_height
        if percentage == 100:
            fill = "#f9e4fa"
            font = bold_font
        else:
            fill = "#ffffff" if index % 2 == 0 else "#eeeeee"
            font = regular_font
        draw.rectangle((0, top, WIDTH, top + row_height - 1), fill=fill)
        _row_text(draw, x=8, top=top, height=row_height, text=f"{percentage}%", font=font)
        _row_text(
            draw,
            x=159,
            top=top,
            height=row_height,
            text=str(ranking_count(total, percentage)),
            font=font,
        )

    draw.rectangle((0, 424, WIDTH, 429), fill="black")
    timestamp_text = (
        f"{generated_at.year}/{generated_at.month}/{generated_at.day} "
        f"{generated_at.hour}:{generated_at:%M}"
    )
    timestamp_font = _font(27, bold=True, condensed=True)
    _centered_text(draw, (152, 450), timestamp_text, timestamp_font, "white")

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


class RankingService:
    """Generates ranking image artifacts."""

    def create(self, total: int, card_type: CardType, car: str) -> RankingImage:
        generated_at = datetime.now().astimezone()
        content = render_ranking(
            total,
            card_type,
            car,
            generated_at=generated_at,
        )
        return RankingImage(content=content, filename="ranking.png")
