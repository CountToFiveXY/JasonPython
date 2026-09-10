import unittest
from unittest.mock import patch

from src.routers.url_shortening import (
    REDIS_KEY_PREFIX,
    ShortenRequest,
    redirect_short_url,
    shorten_url,
)
from fastapi import HTTPException


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.get_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
    ) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

class UrlShorteningTests(unittest.IsolatedAsyncioTestCase):
    async def test_stores_generated_code(self) -> None:
        redis = FakeRedis()

        with patch("src.routers.url_shortening.generate_short_code", return_value="Ab12Cd34"):
            request = ShortenRequest(url="https://example.com/long")
            result = await shorten_url(request, redis)

        self.assertEqual(result.short_url, "go/Ab12Cd34")
        self.assertEqual(
            redis.values[f"{REDIS_KEY_PREFIX}Ab12Cd34"],
            "https://example.com/long",
        )

    async def test_retries_when_generated_code_is_already_used(self) -> None:
        redis = FakeRedis(
            {f"{REDIS_KEY_PREFIX}Ab12Cd34": "https://first.example.com/"}
        )

        with patch(
            "src.routers.url_shortening.generate_short_code",
            side_effect=["Ab12Cd34", "Zx98Yw76"],
        ):
            request = ShortenRequest(url="https://second.example.com/")
            result = await shorten_url(request, redis)

        self.assertEqual(result.short_url, "go/Zx98Yw76")
        self.assertEqual(
            redis.values[f"{REDIS_KEY_PREFIX}Ab12Cd34"],
            "https://first.example.com/",
        )
        self.assertEqual(
            redis.values[f"{REDIS_KEY_PREFIX}Zx98Yw76"],
            "https://second.example.com/",
        )

    async def test_redirect_validates_before_redis_lookup(self) -> None:
        redis = FakeRedis()

        with self.assertRaises(HTTPException) as raised:
            await redirect_short_url("bad", redis)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(redis.get_calls, [])

    async def test_redirect_returns_not_found_for_unknown_code(self) -> None:
        redis = FakeRedis()

        with self.assertRaises(HTTPException) as raised:
            await redirect_short_url("Ab12Cd34", redis)

        self.assertEqual(raised.exception.status_code, 404)

    async def test_redirect_page_opens_original_url(self) -> None:
        original_url = "https://example.com/a/long/path"
        redis = FakeRedis({f"{REDIS_KEY_PREFIX}Ab12Cd34": original_url})

        response = await redirect_short_url("Ab12Cd34", redis)
        body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('window.open(destination, "_blank")', body)
        self.assertIn(original_url, body)
        self.assertIn("window.location.replace(destination)", body)


if __name__ == "__main__":
    unittest.main()
