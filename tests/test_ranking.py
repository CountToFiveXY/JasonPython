import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

from routers.ranking import (
    CardType,
    PERCENTAGES,
    RankingRequest,
    ranking_count,
    render_ranking,
    save_to_desktop,
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

    def test_save_to_desktop_writes_timestamped_png(self) -> None:
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        generated_at = datetime(
            2026, 8, 23, 3, 11, tzinfo=ZoneInfo("America/Los_Angeles")
        )
        request = RankingRequest(total=100, type=CardType.CH, car="Car 7")
        with TemporaryDirectory() as temporary_home, patch(
            "routers.ranking.Path.home", return_value=Path(temporary_home)
        ):
            output = save_to_desktop(b"png-data", request, generated_at)

            self.assertEqual(output.read_bytes(), b"png-data")
            self.assertEqual(output.parent.name, "Desktop")
            self.assertEqual(output.name, "Car-7_CH_20260823_031100.png")


if __name__ == "__main__":
    unittest.main()
