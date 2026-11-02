from fastapi import APIRouter

from app.services.root import get_welcome_message

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return get_welcome_message()
