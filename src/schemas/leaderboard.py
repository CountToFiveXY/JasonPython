"""HTTP response schemas for the Galaxy Lens leaderboard feed."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class LeaderboardTier(BaseModel):
    label: str
    rank: int = Field(ge=0)
    time: str | None = None
    score: float | None = None


class LeaderboardContext(BaseModel):
    id: str
    name: str
    end_date: date
    type: str | None = None
    subtype: str | None = None


class Leaderboard(BaseModel):
    id: int
    name: str
    total_participants: int = Field(ge=0)
    status: str
    updated_at: datetime
    tiers: list[LeaderboardTier]
    event: LeaderboardContext | None = None
    season: LeaderboardContext | None = None


class LeaderboardListResponse(BaseModel):
    source: str
    leaderboards: list[Leaderboard]
