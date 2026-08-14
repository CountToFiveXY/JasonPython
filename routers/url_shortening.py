from uuid import uuid4

from fastapi import APIRouter


router = APIRouter(prefix="/tinyUrl", tags=["URL Shortening"])

BASE26_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def base26_encode(number: int) -> str:
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return BASE26_ALPHABET[0]

    encoded = ""
    while number:
        number, remainder = divmod(number, len(BASE26_ALPHABET))
        encoded = BASE26_ALPHABET[remainder] + encoded
    return encoded


@router.get("")
def shorten_url(url: str) -> dict[str, str]:
    short_code = base26_encode(uuid4().int)
    return {"original_url": url, "short_code": short_code}
