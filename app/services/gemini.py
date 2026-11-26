import os
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

from app.services.chat import chat_with_provider
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT

load_dotenv()

GEMINI_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def _call_gemini(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    messages: list[dict[str, str]],
    json_mode: bool = False,
) -> dict[str, Any]:
    system_instructions = [
        message["content"] for message in messages if message["role"] == "system"
    ]
    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}],
        }
        for message in messages
        if message["role"] != "system"
    ]
    generation_config: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        generation_config["responseMimeType"] = "application/json"
    if max_tokens is not None:
        generation_config["maxOutputTokens"] = max_tokens

    request_body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    if model.startswith("gemma-"):
        if system_instructions and contents:
            contents[0]["parts"][0]["text"] = "\n\n".join(
                [*system_instructions, contents[0]["parts"][0]["text"]]
            )
    else:
        request_body["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_instructions)}]
        }

    try:
        response = requests.post(
            GEMINI_GENERATE_CONTENT_URL.format(model=quote(model, safe="-_.")),
            headers={"x-goog-api-key": api_key},
            json=request_body,
            timeout=(10, 120),
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the Gemini API.",
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
            detail = "Gemini đang giới hạn yêu cầu hoặc tài khoản đã chạm hạn mức (HTTP 429)."
        else:
            detail = f"Gemini API returned HTTP {response.status_code}."
        if provider_message:
            detail = f"{detail} {provider_message[:500]}"
        raise HTTPException(status_code=502, detail=detail)

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini API returned invalid JSON.",
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Gemini API returned an invalid response.")
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise HTTPException(
            status_code=502,
            detail="Gemini API response did not contain a candidate.",
        )
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    text = (
        "".join(
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if isinstance(parts, list)
        else ""
    )
    if not text:
        raise HTTPException(
            status_code=502,
            detail="Gemini API response did not contain text content.",
        )
    usage = result.get("usageMetadata")
    return {
        "content": text,
        "usage": usage if isinstance(usage, dict) else None,
    }


def chat_with_gemini(
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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured.",
        )
    return chat_with_provider(
        provider_name="Gemini",
        api_key=api_key,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        generate_response=_call_gemini,
        web_search_enabled=web_search_enabled,
        max_web_pages=max_web_pages,
        use_cross_encoder=use_cross_encoder,
        cache_lookup_enabled=cache_lookup_enabled,
        cache_write_enabled=cache_write_enabled,
        pre_rerank_count=pre_rerank_count,
        result_count=result_count,
    )
