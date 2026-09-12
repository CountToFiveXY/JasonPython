"""HTTP schemas for URL shortening."""

from typing import Annotated

from fastapi import Path
from pydantic import BaseModel, Field, HttpUrl

ShortKey = Annotated[
    str,
    Path(
        min_length=8,
        max_length=8,
        pattern=r"^[0-9A-Za-z]{8}$",
        alias="shortKey",
        description="Eight-character short key",
    ),
]


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_url: str = Field(serialization_alias="shortUrl")
