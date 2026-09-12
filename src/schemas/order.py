"""HTTP schemas for the order API."""

from pydantic import BaseModel, Field, field_validator

from src.entity import Order


class OrderRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("user_id must not be blank")
        return value


class OrderResponse(Order):
    workflow_id: str
