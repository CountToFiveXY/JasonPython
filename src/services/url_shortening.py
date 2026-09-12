"""URL shortening use cases."""

import secrets
import string
from urllib.parse import urlsplit

from redis.asyncio import Redis


SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
SHORT_CODE_LENGTH = 8
MAX_GENERATION_ATTEMPTS = 5
REDIS_KEY_PREFIX = "short_url:"


class InvalidShortCodeError(ValueError):
    pass


class InvalidStoredUrlError(ValueError):
    pass


class ShortCodeGenerationError(RuntimeError):
    pass


class ShortUrlNotFoundError(LookupError):
    pass


def generate_short_code() -> str:
    return "".join(
        secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH)
    )


def validate_short_code(code: str) -> None:
    if len(code) != SHORT_CODE_LENGTH or any(
        character not in SHORT_CODE_ALPHABET for character in code
    ):
        raise InvalidShortCodeError(
            "Short code must contain exactly eight letters or digits"
        )


class UrlShorteningService:
    """Stores and resolves short URLs through Redis."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def shorten(self, url: str) -> str:
        for _ in range(MAX_GENERATION_ATTEMPTS):
            code = generate_short_code()
            was_created = await self._redis.set(
                f"{REDIS_KEY_PREFIX}{code}",
                url,
                nx=True,
            )
            if was_created:
                return f"go/{code}"

        raise ShortCodeGenerationError("Could not generate a unique code")

    async def resolve(self, short_code: str) -> str:
        validate_short_code(short_code)
        original_url = await self._redis.get(f"{REDIS_KEY_PREFIX}{short_code}")
        if original_url is None:
            raise ShortUrlNotFoundError("Short URL not found")

        parsed_url = urlsplit(original_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise InvalidStoredUrlError("Stored URL is not redirectable")
        return original_url
