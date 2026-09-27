"""HTTP schemas for ranking cards and the Galaxy Lens leaderboard feed."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from src.entity import CardType


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


class GalaxyLeaderboardTier(BaseModel):
    label: str
    rank: int = Field(ge=0)
    time: str | None = None


class GalaxyLeaderboardContext(BaseModel):
    id: str
    name: str
    end_date: date
    type: str | None = None
    subtype: str | None = None


class GalaxyLeaderboard(BaseModel):
    id: int
    name: str
    total_participants: int = Field(ge=0)
    status: str
    updated_at: datetime
    tiers: list[GalaxyLeaderboardTier]
    event: GalaxyLeaderboardContext | None = None
    season: GalaxyLeaderboardContext | None = None


class GalaxyLeaderboardListResponse(BaseModel):
    source: str
    leaderboards: list[GalaxyLeaderboard]
