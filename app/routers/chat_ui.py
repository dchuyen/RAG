from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services.chat_ui import get_chat_page_path

router = APIRouter()


@router.get("/chat", include_in_schema=False)
def groq_chat_page() -> FileResponse:
    return FileResponse(get_chat_page_path(), media_type="text/html")
