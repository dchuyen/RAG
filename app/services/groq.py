import os
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

from app.services.chat import chat_with_provider
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT

load_dotenv()

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.8-27b"


def _call_groq(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    messages: list[dict[str, str]],
    json_mode: bool = False,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        request_body["response_format"] = {"type": "json_object"}
    if max_tokens is not None:
        request_body["max_tokens"] = max_tokens

    try:
        response = requests.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=request_body,
            timeout=(10, 120),
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the Groq API.",
        ) from exc

    if not response.ok:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {}
        provider_error = error_payload.get("error") if isinstance(error_payload, dict) else None
        provider_message = (
            provider_error.get("message")
            if isinstance(provider_error, dict) and isinstance(provider_error.get("message"), str)
            else None
        )
        if response.status_code == 429:
            detail = "Groq đang giới hạn yêu cầu hoặc tài khoản đã chạm hạn mức (HTTP 429)."
        else:
            detail = f"Groq API returned HTTP {response.status_code}."
        if provider_message:
            detail = f"{detail} {provider_message[:500]}"
        raise HTTPException(status_code=502, detail=detail)

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Groq API returned invalid JSON.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Groq API returned an invalid response.")
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise HTTPException(
            status_code=502,
            detail="Groq API response did not contain a choice.",
        )
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content:
        raise HTTPException(
            status_code=502,
            detail="Groq API response did not contain text content.",
        )
    usage = result.get("usage")
    return {
        "content": content,
        "usage": usage if isinstance(usage, dict) else None,
    }


def chat_with_groq(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    web_search_enabled: bool = True,
    max_web_pages: int = 10,
    use_cross_encoder: bool = True,
    cache_lookup_enabled: bool = False,
    cache_write_enabled: bool = False,
    pre_rerank_count: int = PRE_RERANK_COUNT,
    result_count: int = RESULT_COUNT,
) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured.",
        )
    return chat_with_provider(
        provider_name="Groq",
        api_key=api_key,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        generate_response=_call_groq,
        web_search_enabled=web_search_enabled,
        max_web_pages=max_web_pages,
        use_cross_encoder=use_cross_encoder,
        cache_lookup_enabled=cache_lookup_enabled,
        cache_write_enabled=cache_write_enabled,
        pre_rerank_count=pre_rerank_count,
        result_count=result_count,
    )
