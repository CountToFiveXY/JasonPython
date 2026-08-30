import unittest
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from routers.ranking import (
    CardType,
    PERCENTAGES,
    RankingRequest,
    _fitted_font,
    ranking_count,
    render_ranking,
)


class RankingTests(unittest.TestCase):
    def test_percentage_rows_match_each_type(self) -> None:
        self.assertEqual(PERCENTAGES[CardType.CH], (1, 5, 25, 50, 75, 100))
        self.assertEqual(PERCENTAGES[CardType.SP], (1, 10, 25, 50, 75, 100))
        self.assertEqual(PERCENTAGES[CardType.SE], (5, 10, 25, 50, 75, 100))

    def test_counts_use_round_half_up(self) -> None:
        self.assertEqual(ranking_count(28_916, 5), 1_446)
        self.assertEqual(ranking_count(30_910, 25), 7_728)
        self.assertEqual(ranking_count(8_982, 5), 449)

    def test_renderer_returns_reference_sized_png(self) -> None:
        png = render_ranking(
            RankingRequest(total=28_916, type=CardType.CH, car="Galaxy"),
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
            RankingRequest(total=100, type=CardType.SE, car="银河之光"),
            generated_at=datetime(2026, 8, 29, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        image = Image.open(BytesIO(png))
        self.assertEqual(image.size, (304, 506))

if __name__ == "__main__":
    unittest.main()
