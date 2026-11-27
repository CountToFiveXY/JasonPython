"""Request and response models for remote Asphalt tasks."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AsphaltTaskType(str, Enum):
    RESET = "RESET"
    REFILL_ADS = "REFILL_ADS"
    START_GAME = "START_GAME"
    CLOSE_GAME = "CLOSE_GAME"
    WINDOW = "WINDOW"
    MUTE = "MUTE"


class AsphaltTaskRequest(BaseModel):
    type: AsphaltTaskType
    repeat: int | None = Field(default=None, ge=1, le=99)

    track_completion: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def validate_repeat(self) -> "AsphaltTaskRequest":
        if self.track_completion and self.type not in (AsphaltTaskType.RESET, AsphaltTaskType.CLOSE_GAME):
            raise ValueError("track_completion is only supported for RESET and CLOSE_GAME")
        if self.type != AsphaltTaskType.REFILL_ADS and self.repeat is not None:
            raise ValueError("repeat is only supported for REFILL_ADS")
        if self.type == AsphaltTaskType.REFILL_ADS and self.repeat is None:
            self.repeat = 8
        return self


class AsphaltTaskResponse(AsphaltTaskRequest):
    topic: str
    message_id: str
    task_id: UUID | None = None


class RefillStatus(str, Enum):
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class RefillResult(BaseModel):
    task_id: UUID
    status: RefillStatus
    error: str | None = Field(default=None, max_length=500)


class AsphaltTaskSnapshot(RefillResult):
    type: AsphaltTaskType


class AsphaltTaskHistoryEntry(AsphaltTaskSnapshot):
    requested_at: datetime
    repeat: int | None = None
