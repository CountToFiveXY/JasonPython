"""Request and response models for remote Asphalt tasks."""

from enum import Enum

from pydantic import BaseModel


class AsphaltTaskType(str, Enum):
    RESET = "RESET"
    REFILL_ADS = "REFILL_ADS"


class AsphaltTaskRequest(BaseModel):
    type: AsphaltTaskType


class AsphaltTaskResponse(AsphaltTaskRequest):
    topic: str
    message_id: str
