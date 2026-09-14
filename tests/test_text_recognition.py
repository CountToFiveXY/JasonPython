import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from google.api_core.exceptions import PermissionDenied

from src.routers.text_recognition import read_text
from src.services.text_recognition import (
    INVALID_ARGUMENT,
    MAX_IMAGE_BYTES,
    ImageTooLargeError,
    TextRecognitionService,
    TextRecognitionUnavailableError,
    UnreadableImageError,
)


def paragraph(text: str, *, left: int, top: int, confidence: float = 0.97):
    """A Vision paragraph, shaped like the protobuf response."""

    words = [
        SimpleNamespace(symbols=[SimpleNamespace(text=character) for character in word])
        for word in text.split(" ")
    ]
    vertices = [SimpleNamespace(x=left, y=top), SimpleNamespace(x=left + 100, y=top + 20)]
    return SimpleNamespace(
        words=words,
        confidence=confidence,
        bounding_box=SimpleNamespace(vertices=vertices),
    )


def annotation(paragraphs, text: str = ""):
    return SimpleNamespace(
        text=text or "\n".join(" ".join(
            "".join(s.text for s in word.symbols) for word in p.words
        ) for p in paragraphs),
        pages=[SimpleNamespace(blocks=[SimpleNamespace(paragraphs=paragraphs)])],
    )


class FakeVision:
    def __init__(
        self,
        paragraphs=None,
        error_message: str = "",
        error_code: int = 0,
        raises=None,
    ) -> None:
        self._paragraphs = paragraphs or []
        self._error_message = error_message
        self._error_code = error_code
        self._raises = raises
        self.requests = []

    def document_text_detection(self, image):
        self.requests.append(image)
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(
            error=SimpleNamespace(message=self._error_message, code=self._error_code),
            full_text_annotation=annotation(self._paragraphs),
        )


class TextRecognitionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_a_strip_of_captions_left_to_right(self) -> None:
        # The five captions sit side by side, so they form one row.
        paragraphs = [
            paragraph("NOTRE DAME", left=800, top=60),
            paragraph("WATERSLIDE WHIRL", left=40, top=62),
            paragraph("RAILROAD BUSTLE", left=1600, top=61),
            paragraph("LEAP OF FAITH", left=420, top=60),
            paragraph("FUTURE FUSION", left=1200, top=63),
        ]
        service = TextRecognitionService(FakeVision(paragraphs))

        result = await service.read(b"png-bytes", content_type="image/png")

        self.assertEqual(
            [line.text for line in result.lines],
            [
                "WATERSLIDE WHIRL",
                "LEAP OF FAITH",
                "NOTRE DAME",
                "FUTURE FUSION",
                "RAILROAD BUSTLE",
            ],
        )
        self.assertEqual(result.lines[0].confidence, 0.97)

    async def test_orders_rows_before_columns(self) -> None:
        paragraphs = [
            paragraph("SECOND ROW", left=10, top=400),
            paragraph("FIRST RIGHT", left=900, top=20),
            paragraph("FIRST LEFT", left=10, top=24),
        ]
        service = TextRecognitionService(FakeVision(paragraphs))

        result = await service.read(b"png-bytes")

        self.assertEqual(
            [line.text for line in result.lines],
            ["FIRST LEFT", "FIRST RIGHT", "SECOND ROW"],
        )

    async def test_skips_paragraphs_that_read_as_nothing(self) -> None:
        service = TextRecognitionService(FakeVision([paragraph("", left=0, top=0)]))

        result = await service.read(b"png-bytes")

        self.assertEqual(result.lines, [])

    async def test_rejects_an_empty_image(self) -> None:
        service = TextRecognitionService(FakeVision())

        with self.assertRaises(ValueError):
            await service.read(b"")

    async def test_rejects_an_oversized_image(self) -> None:
        service = TextRecognitionService(FakeVision())

        with self.assertRaises(ImageTooLargeError):
            await service.read(b"x" * (MAX_IMAGE_BYTES + 1))

    async def test_reports_a_disabled_api_as_unavailable(self) -> None:
        service = TextRecognitionService(
            FakeVision(raises=PermissionDenied("Cloud Vision API has not been used"))
        )

        with self.assertRaises(TextRecognitionUnavailableError) as raised:
            await service.read(b"png-bytes")

        self.assertIn("Cloud Vision API", str(raised.exception))

    async def test_reports_an_error_carried_in_the_response(self) -> None:
        service = TextRecognitionService(
            FakeVision(error_message="Internal error", error_code=13)
        )

        with self.assertRaises(TextRecognitionUnavailableError):
            await service.read(b"png-bytes")

    async def test_treats_undecodable_bytes_as_a_bad_request(self) -> None:
        # Vision answers INVALID_ARGUMENT for bytes that are not an image,
        # which is the caller's mistake rather than an outage.
        service = TextRecognitionService(
            FakeVision(error_message="Bad image data.", error_code=INVALID_ARGUMENT)
        )

        with self.assertRaises(UnreadableImageError):
            await service.read(b"not an image")


class TextRecognitionRouterTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def fake_request(content_type: str, payload: bytes):
        async def body() -> bytes:
            return payload

        return SimpleNamespace(headers={"content-type": content_type}, body=body)

    async def test_reads_an_image_posted_as_the_body(self) -> None:
        service = TextRecognitionService(
            FakeVision([paragraph("NOTRE DAME", left=10, top=10)])
        )

        response = await read_text(self.fake_request("image/png", b"png"), service)

        self.assertEqual([line.text for line in response.lines], ["NOTRE DAME"])
        self.assertEqual(response.text, "NOTRE DAME")

    async def test_refuses_a_body_that_is_not_an_image(self) -> None:
        service = TextRecognitionService(FakeVision())

        with self.assertRaises(HTTPException) as raised:
            await read_text(self.fake_request("application/json", b"{}"), service)

        self.assertEqual(raised.exception.status_code, 415)

    async def test_translates_service_errors_into_status_codes(self) -> None:
        oversized = self.fake_request("image/png", b"x" * (MAX_IMAGE_BYTES + 1))
        with self.assertRaises(HTTPException) as raised:
            await read_text(oversized, TextRecognitionService(FakeVision()))
        self.assertEqual(raised.exception.status_code, 413)

        with self.assertRaises(HTTPException) as raised:
            await read_text(
                self.fake_request("image/png", b""), TextRecognitionService(FakeVision())
            )
        self.assertEqual(raised.exception.status_code, 400)

        disabled = TextRecognitionService(FakeVision(raises=PermissionDenied("disabled")))
        with self.assertRaises(HTTPException) as raised:
            await read_text(self.fake_request("image/jpeg", b"jpg"), disabled)
        self.assertEqual(raised.exception.status_code, 503)

        unreadable = TextRecognitionService(
            FakeVision(error_message="Bad image data.", error_code=INVALID_ARGUMENT)
        )
        with self.assertRaises(HTTPException) as raised:
            await read_text(self.fake_request("image/png", b"nope"), unreadable)
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
