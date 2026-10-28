from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
CHAT_PAGE = Path(__file__).resolve().parents[1] / "static" / "groq_chat.html"


@router.get("/chat", include_in_schema=False)
def groq_chat_page() -> FileResponse:
    return FileResponse(CHAT_PAGE, media_type="text/html")
