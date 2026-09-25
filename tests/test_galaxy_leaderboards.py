import json
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException

from src.routers.ranking import list_galaxy_leaderboards
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

    def test_router_maps_upstream_failure_to_bad_gateway(self) -> None:
        class FailingService:
            def fetch(self):
                raise GalaxyLeaderboardError("temporarily unavailable")

        with self.assertRaises(HTTPException) as raised:
            list_galaxy_leaderboards(FailingService())

        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
