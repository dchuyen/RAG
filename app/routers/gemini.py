from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.gemini import DEFAULT_MODEL, chat_with_gemini

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str = DEFAULT_MODEL
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)


@router.post("/chat/gemini")
def gemini_chat(request: ChatRequest) -> dict[str, Any]:
    return chat_with_gemini(
        [message.model_dump() for message in request.messages],
        request.model,
        request.temperature,
        request.max_tokens,
    )
