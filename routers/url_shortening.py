from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis

from database import get_redis


router = APIRouter(tags=["URL Shortening"])

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 8
SHORT_CODE_SPACE = len(BASE62_ALPHABET) ** SHORT_CODE_LENGTH
MAX_GENERATION_ATTEMPTS = 5
REDIS_KEY_PREFIX = "short_url:"


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


@router.get("/tinyUrl")
async def shorten_url(
    url: str,
    redis_client: Redis = Depends(get_redis),
) -> dict[str, str]:
    for _ in range(MAX_GENERATION_ATTEMPTS):
        identifier = uuid4().int % SHORT_CODE_SPACE
        code = base62_encode(identifier).rjust(SHORT_CODE_LENGTH, "0")
        was_created = await redis_client.set(
            f"{REDIS_KEY_PREFIX}{code}",
            url,
            nx=True,
        )
        if was_created:
            return {"original_url": url, "short_code": f"go/{code}"}

    raise HTTPException(status_code=503, detail="Could not generate a unique code")


@router.get("/go/{code}", response_class=RedirectResponse)
async def resolve_short_url(
    code: str,
    redis_client: Redis = Depends(get_redis),
) -> RedirectResponse:
    original_url = await redis_client.get(f"{REDIS_KEY_PREFIX}{code}")
    if original_url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return RedirectResponse(original_url)
