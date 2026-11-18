"""Request and response models for remote Asphalt tasks."""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class AsphaltTaskType(str, Enum):
    RESET = "RESET"
    REFILL_ADS = "REFILL_ADS"
    START_GAME = "START_GAME"
    CLOSE_GAME = "CLOSE_GAME"
    WINDOW = "WINDOW"


class AsphaltTaskRequest(BaseModel):
    type: AsphaltTaskType
    repeat: int | None = Field(default=None, ge=1, le=99)

    @model_validator(mode="after")
    def validate_repeat(self) -> "AsphaltTaskRequest":
        if self.type != AsphaltTaskType.REFILL_ADS and self.repeat is not None:
            raise ValueError("repeat is only supported for REFILL_ADS")
        if self.type == AsphaltTaskType.REFILL_ADS and self.repeat is None:
            self.repeat = 8
        return self


class AsphaltTaskResponse(AsphaltTaskRequest):
    topic: str
    message_id: str
