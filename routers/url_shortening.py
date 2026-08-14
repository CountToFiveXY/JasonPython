from uuid import uuid4

from fastapi import APIRouter


router = APIRouter(prefix="/tinyUrl", tags=["URL Shortening"])

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 8
SHORT_CODE_SPACE = len(BASE62_ALPHABET) ** SHORT_CODE_LENGTH


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


@router.get("")
def shorten_url(url: str) -> dict[str, str]:
    identifier = uuid4().int % SHORT_CODE_SPACE
    encoded_identifier = base62_encode(identifier).rjust(SHORT_CODE_LENGTH, "0")
    short_code = f"go/{encoded_identifier}"
    return {"original_url": url, "short_code": short_code}
