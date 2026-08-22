import html
import json
from hashlib import sha256
from typing import Annotated
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl
from redis.asyncio import Redis

from infrastructure.clients import get_redis


router = APIRouter(tags=["URL Shortening"])

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 8
SHORT_CODE_SPACE = len(BASE62_ALPHABET) ** SHORT_CODE_LENGTH
MAX_GENERATION_ATTEMPTS = 5
REDIS_KEY_PREFIX = "short_url:"
URL_CODE_KEY_PREFIX = "url_code:"
URL_CODE_INDEX_MARKER = "url_code_index:v1"

CREATE_SHORT_CODE_SCRIPT = """
local existing_code = redis.call('GET', KEYS[1])
if existing_code then
    local existing_url = redis.call('GET', ARGV[3] .. existing_code)
    if existing_url == ARGV[1] then
        return existing_code
    end
    redis.call('DEL', KEYS[1])
end

if redis.call('EXISTS', KEYS[2]) == 1 then
    return false
end

redis.call('SET', KEYS[2], ARGV[1])
redis.call('SET', KEYS[1], ARGV[2])
return ARGV[2]
"""

ShortKey = Annotated[
    str,
    Path(
        min_length=SHORT_CODE_LENGTH,
        max_length=SHORT_CODE_LENGTH,
        pattern=r"^[0-9A-Za-z]{8}$",
        alias="shortKey",
        description="Eight-character base-62 short key",
    ),
]


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_key: str = Field(serialization_alias="shortKey")


def base62_encode(number: int) -> str:
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return BASE62_ALPHABET[0]

    encoded = ""
    while number:
        number, remainder = divmod(number, len(BASE62_ALPHABET))
        encoded = BASE62_ALPHABET[remainder] + encoded
    return encoded


def url_code_key(url: str) -> str:
    digest = sha256(url.encode("utf-8")).hexdigest()
    return f"{URL_CODE_KEY_PREFIX}{digest}"


def validate_short_code(code: str) -> None:
    if len(code) != SHORT_CODE_LENGTH or any(
        character not in BASE62_ALPHABET for character in code
    ):
        raise HTTPException(
            status_code=400,
            detail="Short code must contain exactly eight base-62 characters",
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


async def ensure_url_code_index(redis_client: Redis) -> None:
    if await redis_client.get(URL_CODE_INDEX_MARKER) is not None:
        return

    async for key in redis_client.scan_iter(match=f"{REDIS_KEY_PREFIX}*"):
        original_url = await redis_client.get(key)
        if original_url is None:
            continue
        code = key.removeprefix(REDIS_KEY_PREFIX)
        await redis_client.set(url_code_key(original_url), code, nx=True)

    await redis_client.set(URL_CODE_INDEX_MARKER, "1")


@router.post("/v1/shorten", response_model=ShortenResponse)
async def shorten_url(
    request: ShortenRequest,
    redis_client: Redis = Depends(get_redis),
) -> ShortenResponse:
    url = str(request.url)
    await ensure_url_code_index(redis_client)

    reverse_key = url_code_key(url)
    existing_code = await redis_client.get(reverse_key)
    if existing_code is not None:
        stored_url = await redis_client.get(f"{REDIS_KEY_PREFIX}{existing_code}")
        if stored_url == url:
            return ShortenResponse(short_key=existing_code)
        await redis_client.delete(reverse_key)

    for _ in range(MAX_GENERATION_ATTEMPTS):
        identifier = uuid4().int % SHORT_CODE_SPACE
        code = base62_encode(identifier).rjust(SHORT_CODE_LENGTH, "0")
        stored_code = await redis_client.eval(
            CREATE_SHORT_CODE_SCRIPT,
            2,
            reverse_key,
            f"{REDIS_KEY_PREFIX}{code}",
            url,
            code,
            REDIS_KEY_PREFIX,
        )
        if stored_code is not None:
            return ShortenResponse(short_key=stored_code)

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
