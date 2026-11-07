import json
import os
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

from app.services.semantic_search import semantic_search
from app.services.source_merge import render_merged_documents_as_markdown
from app.services.system_rule import SYSTEM_RULE

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


def _parse_assistant_action(
    content: str,
) -> tuple[Literal["answer", "clarify", "search"], str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini API returned an invalid action response.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Gemini API returned an invalid action response.")

    action = payload.get("action")
    field_by_action = {"answer": "answer", "clarify": "question", "search": "query"}
    if not isinstance(action, str) or action not in field_by_action:
        raise HTTPException(status_code=502, detail="Gemini API returned an unknown action.")

    value = payload.get(field_by_action[action])
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API returned an empty {field_by_action[action]}.",
        )
    return action, value.strip()


def _format_search_results(search_response: dict[str, Any]) -> str:
    results = search_response["results"]
    if not results:
        return "Không tìm thấy tài liệu phù hợp. Hãy nói rõ là chưa tìm thấy nguồn để xác nhận."

    best_result = max(results, key=lambda result: result["relevance_score"])
    return render_merged_documents_as_markdown([best_result])


def chat_with_gemini(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured.",
        )

    request_messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_RULE}\n"
                "Thời gian hiện tại theo múi giờ máy chủ là "
                f"{datetime.now().astimezone().isoformat(timespec='seconds')}."
            ),
        },
        *messages,
    ]
    result = _call_gemini(
        api_key,
        model,
        temperature,
        max_tokens,
        request_messages,
        json_mode=True,
    )
    action, action_value = _parse_assistant_action(result["content"])

    if action == "search":
        search_query = action_value
        search_response = semantic_search(query=search_query)
        request_messages.extend(
            [
                {"role": "assistant", "content": result["content"]},
                {
                    "role": "user",
                    "content": (
                        f"Kết quả semantic search cho truy vấn '{search_query}':\n"
                        f"{_format_search_results(search_response)}\n\n"
                        "Hãy trả lời câu hỏi ban đầu dựa trên các nguồn này. "
                        "Không phát ra yêu cầu search lần nữa trong lượt trả lời này."
                    ),
                },
            ]
        )
        result = _call_gemini(api_key, model, temperature, max_tokens, request_messages)
        message = result["content"]
    else:
        message = action_value

    return {
        "message": message,
        "model": model,
        "usage": result["usage"],
    }
