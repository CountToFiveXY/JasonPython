"""Image-to-text HTTP endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.dependencies import get_text_recognition_service
from src.schemas import TextLineResponse, TextRecognitionResponse
from src.services import TextRecognitionService
from src.services.text_recognition import (
    ImageTooLargeError,
    TextRecognitionUnavailableError,
)


router = APIRouter(prefix="/v1/text-recognition", tags=["Text Recognition"])


@router.post("", response_model=TextRecognitionResponse)
async def read_text(
    request: Request,
    service: TextRecognitionService = Depends(get_text_recognition_service),
) -> TextRecognitionResponse:
    """Read the words in a posted image.

    The image is the raw request body, so a client sends the bytes it already
    has with an `image/*` content type instead of encoding a multipart form.
    """

    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Send the image as the request body with an image/* content type",
        )

    payload = await request.body()
    try:
        recognized = await service.read(payload, content_type=content_type)
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TextRecognitionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TextRecognitionResponse(
        text=recognized.text,
        lines=[
            TextLineResponse(text=line.text, confidence=line.confidence)
            for line in recognized.lines
        ],
    )
