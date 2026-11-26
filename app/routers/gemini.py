from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.gemini import DEFAULT_MODEL, chat_with_gemini
from app.services.groq import DEFAULT_MODEL as GROQ_DEFAULT_MODEL, chat_with_groq
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    web_search_enabled: bool = True
    max_web_pages: int = Field(default=10, ge=1, le=50)
    use_cross_encoder: bool = True
    cache_lookup_enabled: bool = False
    cache_write_enabled: bool = False
    pre_rerank_count: int = Field(default=PRE_RERANK_COUNT, ge=1, le=50)
    result_count: int = Field(default=RESULT_COUNT, ge=1, le=50)


@router.post("/chat/gemini")
def gemini_chat(request: ChatRequest) -> dict[str, Any]:
    return chat_with_gemini(
        messages=[message.model_dump() for message in request.messages],
        model=request.model or DEFAULT_MODEL,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        web_search_enabled=request.web_search_enabled,
        max_web_pages=request.max_web_pages,
        use_cross_encoder=request.use_cross_encoder,
        cache_lookup_enabled=request.cache_lookup_enabled,
        cache_write_enabled=request.cache_write_enabled,
        pre_rerank_count=request.pre_rerank_count,
        result_count=request.result_count,
    )


@router.post("/chat/groq")
def groq_chat(request: ChatRequest) -> dict[str, Any]:
    return chat_with_groq(
        messages=[message.model_dump() for message in request.messages],
        model=request.model or GROQ_DEFAULT_MODEL,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        web_search_enabled=request.web_search_enabled,
        max_web_pages=request.max_web_pages,
        use_cross_encoder=request.use_cross_encoder,
        cache_lookup_enabled=request.cache_lookup_enabled,
        cache_write_enabled=request.cache_write_enabled,
        pre_rerank_count=request.pre_rerank_count,
        result_count=request.result_count,
    )
