import unittest
from types import SimpleNamespace
from unittest.mock import patch

from routers.url_shortening import (
    REDIS_KEY_PREFIX,
    ShortenRequest,
    URL_CODE_INDEX_MARKER,
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

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def scan_iter(self, *, match: str):
        prefix = match.removesuffix("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    async def eval(
        self,
        _script: str,
        _number_of_keys: int,
        reverse_key: str,
        short_key: str,
        url: str,
        code: str,
        short_prefix: str,
    ) -> str | None:
        existing_code = self.values.get(reverse_key)
        if existing_code is not None:
            if self.values.get(f"{short_prefix}{existing_code}") == url:
                return existing_code
            self.values.pop(reverse_key)
        if short_key in self.values:
            return None
        self.values[short_key] = url
        self.values[reverse_key] = code
        return code


class UrlShorteningTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_code_for_a_newly_stored_url(self) -> None:
        redis = FakeRedis()

        with patch(
            "routers.url_shortening.uuid4",
            side_effect=[SimpleNamespace(int=1), SimpleNamespace(int=2)],
        ):
            request = ShortenRequest(url="https://example.com/long")
            first = await shorten_url(request, redis)
            second = await shorten_url(request, redis)

        self.assertEqual(first.short_key, "00000001")
        self.assertEqual(second.short_key, first.short_key)
        self.assertEqual(len(first.short_key), 8)

    async def test_builds_reverse_lookup_for_a_legacy_mapping(self) -> None:
        redis = FakeRedis(
            {f"{REDIS_KEY_PREFIX}Ab12Cd34": "https://example.com/existing"}
        )

        request = ShortenRequest(url="https://example.com/existing")
        result = await shorten_url(request, redis)

        self.assertEqual(result.short_key, "Ab12Cd34")
        self.assertEqual(redis.values[URL_CODE_INDEX_MARKER], "1")

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
