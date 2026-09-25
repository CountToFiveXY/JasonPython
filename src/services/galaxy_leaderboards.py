"""Read-only access to the public Galaxy Lens leaderboard feed."""

import json
import os
import ssl
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


DEFAULT_SUPABASE_URL = "https://jflpzvmpjeeqfkvqppuq.supabase.co"
# This is Supabase's public anonymous browser key, not a service-role secret.
DEFAULT_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmbHB6dm1wamVlcWZrdnFwcHVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc4NDE1NDcsImV4cCI6MjA3MzQxNzU0N30."
    "WM-5QGlrD1c7-AP7l61FTS79dJQlFAzt_VHQFw1MuNo"
)


class GalaxyLeaderboardError(RuntimeError):
    """Raised when the upstream public feed cannot be read."""


class GalaxyLeaderboardService:
    def __init__(self) -> None:
        self.base_url = os.getenv("GALAXY_LENS_SUPABASE_URL", DEFAULT_SUPABASE_URL)
        self.anon_key = os.getenv("GALAXY_LENS_SUPABASE_ANON_KEY", DEFAULT_ANON_KEY)

    def fetch(self) -> list[dict]:
        leaderboards = self._read_table(
            "leaderboards",
            (
                "id,event_name,bottom_rank,total_participants,tier_ranks,status,"
                "updated_at,associated_event_id,associated_season_id,official_snapshot_id"
            ),
            order="updated_at.desc",
            filters={"status": "eq.active"},
        )
        events = {
            row["id"]: row
            for row in self._read_table("events", "id,name,end_date,type,subtype")
        }
        seasons = {
            row["id"]: row
            for row in self._read_table("seasons", "id,name,end_date")
        }
        snapshots = {
            row["id"]: row
            for row in self._read_table(
                "official_leaderboard_snapshots",
                (
                    "id,metric_type,tiers:official_leaderboard_tiers("
                    "percentage,rank_target,rank,time_text,participant_count)"
                ),
            )
        }
        normalized = [
            self._normalize(
                record,
                events.get(record.get("associated_event_id")),
                seasons.get(record.get("associated_season_id")),
                snapshots.get(record.get("official_snapshot_id")),
            )
            for record in leaderboards
        ]
        normalized.sort(key=lambda row: self._sort_key(row, events))
        return normalized

    def _read_table(
        self,
        table: str,
        select: str,
        *,
        order: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[dict]:
        parameters = {"select": select, "limit": "1000"}
        if order:
            parameters["order"] = order
        if filters:
            parameters.update(filters)
        query = urlencode(parameters)
        request = Request(
            f"{self.base_url}/rest/v1/{table}?{query}",
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.anon_key}",
                "Accept": "application/json",
                "User-Agent": "JasonApp/1.0",
            },
        )
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(request, timeout=12, context=ssl_context) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GalaxyLeaderboardError(
                "Galaxy Lens leaderboard data is temporarily unavailable."
            ) from exc

        if not isinstance(payload, list):
            raise GalaxyLeaderboardError("Galaxy Lens returned an unexpected response.")
        return payload

    @staticmethod
    def _normalize(
        record: dict,
        event: dict | None = None,
        season: dict | None = None,
        snapshot: dict | None = None,
    ) -> dict:
        raw_tiers = record.get("tier_ranks") or {}
        snapshot_times = GalaxyLeaderboardService._snapshot_times(snapshot)
        tiers = []
        for label, rank in raw_tiers.items():
            if rank is None:
                continue
            tiers.append(
                {
                    "label": label,
                    "rank": int(rank),
                    "time": snapshot_times.get(label),
                }
            )
        tiers.sort(key=lambda tier: GalaxyLeaderboardService._tier_sort_key(tier["label"]))
        return {
            "id": int(record["id"]),
            "name": str(record.get("event_name") or "Unnamed leaderboard"),
            "total_participants": int(
                record.get("total_participants") or record.get("bottom_rank") or 0
            ),
            "status": str(record.get("status") or "finished"),
            "updated_at": record["updated_at"],
            "tiers": tiers,
            "event": GalaxyLeaderboardService._context(event),
            "season": GalaxyLeaderboardService._context(season),
        }

    @staticmethod
    def _snapshot_times(snapshot: dict | None) -> dict[str, str]:
        if not snapshot or snapshot.get("metric_type") != "time":
            return {}
        result = {}
        for tier in snapshot.get("tiers") or []:
            percentage = tier.get("percentage")
            rank_target = tier.get("rank_target")
            label = (
                f"{percentage}%"
                if percentage is not None
                else f"rank:{rank_target}" if rank_target is not None else None
            )
            if label and tier.get("time_text"):
                result[label] = str(tier["time_text"])
        return result

    @staticmethod
    def _context(record: dict | None) -> dict | None:
        if not record:
            return None
        return {
            "id": str(record["id"]),
            "name": str(record["name"]),
            "end_date": record["end_date"],
        }

    @staticmethod
    def _sort_key(record: dict, events: dict[str, dict]) -> tuple[float, int]:
        updated = datetime.fromisoformat(record["updated_at"].replace("Z", "+00:00"))
        minute = int(updated.timestamp() // 60)
        event = record.get("event")
        source = events.get(event["id"]) if event else None
        event_type = str((source or {}).get("type") or "").upper()
        priority = {
            "SPECIAL_EVENT": 0,
            "STAR_HUNT": 1,
            "EPIC_HUNT": 1,
            "CAR_HUNT": 1,
            "LIMITED_TIME_EVENT": 2,
        }.get(event_type, 3)
        return (-minute, priority)

    @staticmethod
    def _tier_sort_key(label: str) -> tuple[int, float]:
        if label.startswith("rank:"):
            try:
                return (0, float(label.removeprefix("rank:")))
            except ValueError:
                return (0, float("inf"))
        try:
            return (1, float(label.removesuffix("%")))
        except ValueError:
            return (1, float("inf"))
