import json
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException

from src.main import app
from src.routers.galaxy_leaderboard import list_galaxy_leaderboards
from src.services.galaxy_leaderboards import (
    GalaxyLeaderboardError,
    GalaxyLeaderboardService,
)


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class GalaxyLeaderboardTests(unittest.TestCase):
    def test_leaderboard_and_gauntlet_use_distinct_api_names(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("/v1/leaderboard", paths)
        self.assertIn("/v1/gauntlet/maps", paths)
        self.assertNotIn("/v1/ranking/leaderboards", paths)
        self.assertNotIn("/v1/leaderboard/maps", paths)

    def test_fetch_normalizes_and_sorts_tiers(self) -> None:
        payload = [
            {
                "id": 249,
                "event_name": "啤酒节",
                "bottom_rank": 192865,
                "total_participants": None,
                "tier_ranks": {"100%": 192865, "10%": 19286, "rank:1": 1},
                "status": "active",
                "updated_at": "2026-09-25T04:00:05+00:00",
            }
        ]
        responses = [
            FakeResponse(json.dumps(payload).encode()),
            FakeResponse(
                json.dumps(
                    [{"id": "event-1", "name": "OKTOBER FAST TLE", "end_date": "2026-09-30", "type": "LIMITED_TIME_EVENT", "subtype": None}]
                ).encode()
            ),
            FakeResponse(
                json.dumps(
                    [{"id": "season-1", "name": "SUNSET SPEEDWAY", "end_date": "2026-10-14"}]
                ).encode()
            ),
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": "snapshot-1",
                            "metric_type": "time",
                            "tiers": [
                                {
                                    "percentage": 10,
                                    "rank_target": None,
                                    "rank": 19286,
                                    "time_text": "1:04.626",
                                    "score": None,
                                    "participant_count": 19286,
                                }
                            ],
                        }
                    ]
                ).encode()
            ),
        ]
        payload[0]["associated_event_id"] = "event-1"
        payload[0]["associated_season_id"] = "season-1"
        payload[0]["official_snapshot_id"] = "snapshot-1"
        responses[0] = FakeResponse(json.dumps(payload).encode())

        with patch("src.services.galaxy_leaderboards.urlopen", side_effect=responses):
            result = GalaxyLeaderboardService().fetch()

        self.assertEqual(result[0]["name"], "啤酒节")
        self.assertEqual(result[0]["total_participants"], 192865)
        self.assertEqual(
            [tier["label"] for tier in result[0]["tiers"]],
            ["rank:1", "10%", "100%"],
        )
        self.assertEqual(result[0]["event"]["name"], "OKTOBER FAST TLE")
        self.assertEqual(result[0]["event"]["type"], "LIMITED_TIME_EVENT")
        self.assertEqual(result[0]["season"]["name"], "SUNSET SPEEDWAY")
        self.assertEqual(result[0]["tiers"][1]["time"], "1:04.626")
        self.assertIsNone(result[0]["tiers"][1]["score"])

    def test_fetch_includes_scores_from_score_snapshot(self) -> None:
        responses = [
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": 256,
                            "event_name": "IMS∧聚光灯",
                            "bottom_rank": 39198,
                            "total_participants": 39198,
                            "tier_ranks": {"1%": 391, "100%": 39198},
                            "status": "active",
                            "updated_at": "2026-09-26T03:00:00+00:00",
                            "associated_event_id": "spotlight-1",
                            "associated_season_id": None,
                            "official_snapshot_id": "snapshot-score",
                        }
                    ]
                ).encode()
            ),
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": "spotlight-1",
                            "name": "IMS Spotlight",
                            "end_date": "2026-10-14",
                            "type": "LIMITED_TIME_EVENT",
                            "subtype": "spotlight",
                        }
                    ]
                ).encode()
            ),
            FakeResponse(b"[]"),
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": "snapshot-score",
                            "metric_type": "score",
                            "tiers": [
                                {
                                    "percentage": 1,
                                    "rank_target": None,
                                    "rank": 391,
                                    "time_text": None,
                                    "score": 14519,
                                    "participant_count": 39198,
                                },
                                {
                                    "percentage": 100,
                                    "rank_target": None,
                                    "rank": 39198,
                                    "time_text": None,
                                    "score": 880,
                                    "participant_count": 39198,
                                },
                            ],
                        }
                    ]
                ).encode()
            ),
        ]

        with patch("src.services.galaxy_leaderboards.urlopen", side_effect=responses):
            result = GalaxyLeaderboardService().fetch()

        self.assertEqual(result[0]["tiers"][0]["rank"], 391)
        self.assertEqual(result[0]["tiers"][0]["score"], 14519.0)
        self.assertIsNone(result[0]["tiers"][0]["time"])
        self.assertEqual(result[0]["tiers"][1]["score"], 880.0)

    def test_router_maps_upstream_failure_to_bad_gateway(self) -> None:
        class FailingService:
            def fetch(self):
                raise GalaxyLeaderboardError("temporarily unavailable")

        with self.assertRaises(HTTPException) as raised:
            list_galaxy_leaderboards(FailingService())

        self.assertEqual(raised.exception.status_code, 502)

    def test_fetch_excludes_grand_prix_leaderboards(self) -> None:
        responses = [
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": 300,
                            "event_name": "KIMERA EVO37 GRAND PRIX",
                            "bottom_rank": 1000,
                            "total_participants": 1000,
                            "tier_ranks": {"1%": 10, "100%": 1000},
                            "status": "active",
                            "updated_at": "2026-09-26T12:00:00+00:00",
                            "associated_event_id": "gp-1",
                            "associated_season_id": None,
                            "official_snapshot_id": None,
                        }
                    ]
                ).encode()
            ),
            FakeResponse(
                json.dumps(
                    [
                        {
                            "id": "gp-1",
                            "name": "KIMERA EVO37 GRAND PRIX",
                            "end_date": "2026-10-09",
                            "type": "GRAND_PRIX",
                            "subtype": None,
                        }
                    ]
                ).encode()
            ),
            FakeResponse(b"[]"),
            FakeResponse(b"[]"),
        ]

        with patch("src.services.galaxy_leaderboards.urlopen", side_effect=responses):
            result = GalaxyLeaderboardService().fetch()

        self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()
