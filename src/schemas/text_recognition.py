"""HTTP schemas for reading text out of an image."""

from pydantic import BaseModel, Field


class TextLineResponse(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class TextRecognitionResponse(BaseModel):
    #: Everything that was read, as one block.
    text: str
    #: The same words split into lines, in reading order.
    lines: list[TextLineResponse]
