from fastapi import APIRouter


router = APIRouter(prefix="/message", tags=["Messages"])


@router.get("")
def print_message() -> str:
    message = "Hello from FastAPI!"
    return message
