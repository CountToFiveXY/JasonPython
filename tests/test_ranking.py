import unittest
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image

from routers.ranking import (
    CardType,
    PERCENTAGES,
    RankingRequest,
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

if __name__ == "__main__":
    unittest.main()
