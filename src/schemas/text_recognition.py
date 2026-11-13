"""HTTP schemas for reading text out of an image."""

from pydantic import BaseModel, Field


class TextBoundsResponse(BaseModel):
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class TextLineResponse(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    bounds: TextBoundsResponse | None = None


class TextRecognitionResponse(BaseModel):
    #: Everything that was read, as one block.
    text: str
    #: The same words split into lines, in reading order.
    lines: list[TextLineResponse]
