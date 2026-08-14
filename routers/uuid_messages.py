from uuid import uuid4

from fastapi import APIRouter


router = APIRouter(tags=["UUID Messages"])


@router.get("/")
def extend_text(text: str) -> dict[str, str]:
    identifier = str(uuid4())
    extended_text = f"{text}-{identifier}"
    print(extended_text)
    return {"encoded message": extended_text}
