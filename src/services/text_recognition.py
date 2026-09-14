"""Reading the words out of an image, through Cloud Vision."""

import asyncio
from dataclasses import dataclass

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import vision


#: Images larger than this are refused rather than sent upstream.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
#: google.rpc.Code.INVALID_ARGUMENT, returned for bytes Vision cannot decode.
INVALID_ARGUMENT = 3
#: Lines within this many pixels of each other count as the same row, so a
#: strip of side-by-side captions reads left to right rather than by height.
ROW_TOLERANCE = 24


class ImageTooLargeError(ValueError):
    pass


class UnreadableImageError(ValueError):
    pass


class TextRecognitionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextLine:
    text: str
    confidence: float


@dataclass(frozen=True)
class RecognizedText:
    text: str
    lines: list[TextLine]


def _top(paragraph) -> int:
    return min((vertex.y for vertex in paragraph.bounding_box.vertices), default=0)


def _left(paragraph) -> int:
    return min((vertex.x for vertex in paragraph.bounding_box.vertices), default=0)


def _reading_order(paragraphs: list) -> list:
    """Paragraphs in rows, left to right within each row.

    Rows are found by vertical proximity rather than by bucketing the top
    coordinate: captions sitting side by side rarely align to the pixel, and
    fixed buckets split two that straddle a boundary into separate rows.
    """

    rows: list[list] = []
    for paragraph in sorted(paragraphs, key=_top):
        if rows and _top(paragraph) - _top(rows[-1][0]) <= ROW_TOLERANCE:
            rows[-1].append(paragraph)
        else:
            rows.append([paragraph])

    return [paragraph for row in rows for paragraph in sorted(row, key=_left)]


class TextRecognitionService:
    """Turns an image into the lines of text it contains."""

    def __init__(self, vision_client: vision.ImageAnnotatorClient) -> None:
        self._vision = vision_client

    async def read(self, payload: bytes, *, content_type: str = "") -> RecognizedText:
        if not payload:
            raise ValueError("The image is empty")
        if len(payload) > MAX_IMAGE_BYTES:
            raise ImageTooLargeError(
                f"Images must be {MAX_IMAGE_BYTES // (1024 * 1024)} MB or smaller"
            )
        del content_type  # Cloud Vision detects the format itself.

        try:
            # Document detection rather than plain text detection: it is the
            # only mode that fills in confidence, and on a strip of captions
            # it reads exactly the same words.
            response = await asyncio.to_thread(
                self._vision.document_text_detection,
                image=vision.Image(content=payload),
            )
        except GoogleAPICallError as error:
            raise TextRecognitionUnavailableError(str(error)) from error

        if response.error.message:
            # INVALID_ARGUMENT means the bytes were not a readable image, which
            # is the caller's problem rather than the service being down.
            if response.error.code == INVALID_ARGUMENT:
                raise UnreadableImageError(response.error.message)
            raise TextRecognitionUnavailableError(response.error.message)

        return RecognizedText(
            text=response.full_text_annotation.text.strip(),
            lines=self._lines(response.full_text_annotation),
        )

    @staticmethod
    def _lines(annotation) -> list[TextLine]:
        paragraphs = [
            paragraph
            for page in annotation.pages
            for block in page.blocks
            for paragraph in block.paragraphs
        ]

        lines = []
        for paragraph in _reading_order(paragraphs):
            words = [
                "".join(symbol.text for symbol in word.symbols)
                for word in paragraph.words
            ]
            text = " ".join(word for word in words if word).strip()
            if text:
                lines.append(TextLine(text=text, confidence=round(paragraph.confidence, 3)))
        return lines
