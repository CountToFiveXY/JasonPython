import html
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from src.dependencies import get_url_shortening_service
from src.schemas import ShortenRequest, ShortenResponse, ShortKey
from src.services import UrlShorteningService
from src.services.url_shortening import (
    InvalidShortCodeError,
    InvalidStoredUrlError,
    ShortCodeGenerationError,
    ShortUrlNotFoundError,
)


router = APIRouter(tags=["URL Shortening"])

def build_redirect_page(original_url: str) -> str:
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


@router.post("/v1/shorten", response_model=ShortenResponse)
async def shorten_url(
    request: ShortenRequest,
    service: UrlShorteningService = Depends(get_url_shortening_service),
) -> ShortenResponse:
    try:
        short_url = await service.shorten(str(request.url))
    except ShortCodeGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ShortenResponse(short_url=short_url)


@router.get("/go/{shortKey}", response_class=HTMLResponse)
async def redirect_short_url(
    short_key: ShortKey,
    service: UrlShorteningService = Depends(get_url_shortening_service),
) -> HTMLResponse:
    try:
        original_url = await service.resolve(short_key)
    except InvalidShortCodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ShortUrlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStoredUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HTMLResponse(build_redirect_page(original_url))
