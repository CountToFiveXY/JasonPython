"""HTTP schemas for ranking image generation."""

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
