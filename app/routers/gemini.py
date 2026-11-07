from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.gemini import DEFAULT_MODEL, chat_with_gemini as run_gemini_chat

router = APIRouter(prefix="/chat/gemini", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class GeminiChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)


class GeminiChatResponse(BaseModel):
    message: str
    model: str
    usage: dict[str, Any] | None = None


@router.post("", response_model=GeminiChatResponse)
def chat_with_gemini(payload: GeminiChatRequest) -> GeminiChatResponse:
    response = run_gemini_chat(
        messages=[message.model_dump() for message in payload.messages],
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    return GeminiChatResponse(**response)
