"""Request and response models for Asphalt Legend remote tasks."""

from enum import Enum

from pydantic import BaseModel


class AsphaltLegendTaskType(str, Enum):
    RESET = "RESET"
    REFILL_ADS = "REFILL_ADS"


class AsphaltLegendTaskRequest(BaseModel):
    type: AsphaltLegendTaskType


class AsphaltLegendTaskResponse(AsphaltLegendTaskRequest):
    topic: str
    message_id: str
