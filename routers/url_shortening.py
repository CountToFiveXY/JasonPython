import html
import json
import secrets
import string
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl
from redis.asyncio import Redis

from infrastructure.clients import get_redis


router = APIRouter(tags=["URL Shortening"])

SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
SHORT_CODE_LENGTH = 8
MAX_GENERATION_ATTEMPTS = 5
REDIS_KEY_PREFIX = "short_url:"

ShortKey = Annotated[
    str,
    Path(
        min_length=SHORT_CODE_LENGTH,
        max_length=SHORT_CODE_LENGTH,
        pattern=r"^[0-9A-Za-z]{8}$",
        alias="shortKey",
        description="Eight-character short key",
    ),
]


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_key: str = Field(serialization_alias="shortKey")


def generate_short_code() -> str:
    return "".join(
        secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH)
    )


def validate_short_code(code: str) -> None:
    if len(code) != SHORT_CODE_LENGTH or any(
        character not in SHORT_CODE_ALPHABET for character in code
    ):
        raise HTTPException(
            status_code=400,
            detail="Short code must contain exactly eight letters or digits",
        )


def build_redirect_page(original_url: str) -> str:
    parsed_url = urlsplit(original_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=422, detail="Stored URL is not redirectable")

    safe_link = html.escape(original_url, quote=True)
    javascript_url = (
        json.dumps(original_url)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Opening link</title></head>
<body>
<p>Opening <a href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_link}</a>.</p>
<script>
const destination = {javascript_url};
const newTab = window.open(destination, "_blank");
if (newTab) {{
    try {{ newTab.opener = null; }} catch (error) {{ /* Browser restricted access. */ }}
}} else {{
    window.location.replace(destination);
}}
</script>
</body>
</html>"""


@router.post("/v1/shorten", response_model=ShortenResponse)
async def shorten_url(
    request: ShortenRequest,
    redis_client: Redis = Depends(get_redis),
) -> ShortenResponse:
    url = str(request.url)

    for _ in range(MAX_GENERATION_ATTEMPTS):
        code = generate_short_code()
        was_created = await redis_client.set(
            f"{REDIS_KEY_PREFIX}{code}",
            url,
            nx=True,
        )
        if was_created:
            return ShortenResponse(short_key=code)

    raise HTTPException(status_code=503, detail="Could not generate a unique code")


@router.get("/{shortKey}", response_class=HTMLResponse)
async def redirect_short_url(
    short_key: ShortKey,
    redis_client: Redis = Depends(get_redis),
) -> HTMLResponse:
    validate_short_code(short_key)
    original_url = await redis_client.get(f"{REDIS_KEY_PREFIX}{short_key}")
    if original_url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return HTMLResponse(build_redirect_page(original_url))
