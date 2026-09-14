import unittest
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from src.entity import CardType
from src.services.ranking import (
    CAR_TEXT_CENTER,
    CAR_TEXT_LEFT,
    CAR_TEXT_MAX_HEIGHT,
    CAR_TEXT_MAX_WIDTH,
    CAR_TEXT_RIGHT,
    HEADER_HEIGHT,
    LOGO_ORIGIN,
    LOGO_SIZE,
    PERCENTAGES,
    WIDTH,
    _fitted_font,
    ranking_count,
    render_ranking,
)


class RankingTests(unittest.TestCase):
    def test_percentage_rows_match_each_type(self) -> None:
        self.assertEqual(PERCENTAGES[CardType.CH], (1, 5, 25, 50, 75, 100))
        self.assertEqual(PERCENTAGES[CardType.SP], (1, 10, 25, 50, 75, 100))
        self.assertEqual(PERCENTAGES[CardType.SE], (5, 10, 25, 50, 75, 100))

    def test_car_name_box_fills_the_header_beside_the_logo(self) -> None:
        self.assertGreaterEqual(CAR_TEXT_LEFT, LOGO_ORIGIN[0] + LOGO_SIZE)
        self.assertLessEqual(CAR_TEXT_RIGHT, WIDTH)
        self.assertEqual(CAR_TEXT_MAX_WIDTH, CAR_TEXT_RIGHT - CAR_TEXT_LEFT)
        # Most of the space beside the logo, not a narrow column inside it.
        beside_logo = WIDTH - (LOGO_ORIGIN[0] + LOGO_SIZE)
        self.assertGreater(CAR_TEXT_MAX_WIDTH, beside_logo * 0.8)
        self.assertEqual(CAR_TEXT_CENTER[1], HEADER_HEIGHT // 2)

    def test_longest_allowed_car_name_stays_inside_its_box(self) -> None:
        image = Image.new("RGBA", (WIDTH, HEADER_HEIGHT))
        draw = ImageDraw.Draw(image)
        for name in ["W" * 16, "MMMM MMMM MMMM M", "女武神", "X"]:
            font = _fitted_font(
                draw,
                name,
                maximum_size=52,
                maximum_width=CAR_TEXT_MAX_WIDTH,
                maximum_height=CAR_TEXT_MAX_HEIGHT,
                bold=True,
                condensed=True,
            )
            box = draw.textbbox((0, 0), name, font=font)
            self.assertLessEqual(box[2] - box[0], CAR_TEXT_MAX_WIDTH, name)
            self.assertLessEqual(box[3] - box[1], CAR_TEXT_MAX_HEIGHT, name)

    def test_counts_use_round_half_up(self) -> None:
        self.assertEqual(ranking_count(28_916, 5), 1_446)
        self.assertEqual(ranking_count(30_910, 25), 7_728)
        self.assertEqual(ranking_count(8_982, 5), 449)

    def test_renderer_returns_reference_sized_png(self) -> None:
        png = render_ranking(
            28_916,
            CardType.CH,
            "Galaxy",
            generated_at=datetime(2026, 8, 23, 3, 11, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        image = Image.open(BytesIO(png))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.size, (304, 506))

    def test_long_car_name_shrinks_to_header_width(self) -> None:
        image = Image.new("RGB", (304, 506))
        draw = ImageDraw.Draw(image)
        font = _fitted_font(
            draw,
            "SILVERLIGHT",
            maximum_size=38,
            maximum_width=92,
            maximum_height=48,
            bold=True,
        )
        box = draw.textbbox((0, 0), "SILVERLIGHT", font=font)
        self.assertLessEqual(box[2] - box[0], 92)

    def test_renderer_accepts_simplified_chinese_car_name(self) -> None:
        png = render_ranking(
            100,
            CardType.SE,
            "银河之光",
            generated_at=datetime(2026, 8, 29, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        image = Image.open(BytesIO(png))
        self.assertEqual(image.size, (304, 506))

if __name__ == "__main__":
    unittest.main()
