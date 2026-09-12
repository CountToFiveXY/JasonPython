"""HTTP schemas for health checks."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    redis: str
    kafka: str
