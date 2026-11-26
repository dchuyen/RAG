import json
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Literal

from fastapi import HTTPException

from app.services.markdown_export import render_documents_as_markdown
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT
from app.services.semantic_search import semantic_search
from app.services.system_rule import SYSTEM_RULE


def _parse_assistant_action(
    content: str,
    provider_name: str,
) -> tuple[Literal["answer", "clarify", "search"], str]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} API returned an invalid action response.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} API returned an invalid action response.",
        )

    action = payload.get("action")
    field_by_action = {"answer": "answer", "clarify": "question", "search": "query"}
    if not isinstance(action, str) or action not in field_by_action:
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} API returned an unknown action.",
        )

    value = payload.get(field_by_action[action])
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} API returned an empty {field_by_action[action]}.",
        )
    return action, value.strip()


def _format_search_results(search_response: dict[str, Any], top_k: int = 5) -> str:
    results = search_response.get("results", [])
    if not results:
        return "Không tìm thấy tài liệu phù hợp. Hãy nói rõ là chưa tìm thấy nguồn để xác nhận."

    sorted_results = sorted(results, key=lambda result: result["relevance_score"], reverse=True)
    return render_documents_as_markdown(sorted_results[:top_k])


def chat_with_provider(
    provider_name: str,
    api_key: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int | None,
    generate_response: Callable[..., dict[str, Any]],
    web_search_enabled: bool = True,
    max_web_pages: int = 10,
    use_cross_encoder: bool = True,
    cache_lookup_enabled: bool = False,
    cache_write_enabled: bool = False,
    pre_rerank_count: int = PRE_RERANK_COUNT,
    result_count: int = RESULT_COUNT,
) -> dict[str, Any]:
    request_started = perf_counter()
    search_policy = (
        "Tìm kiếm web đã bị TẮT cho lượt này. Không được chọn hành động search."
        if not web_search_enabled
        else "Tìm kiếm web đã được BẬT."
    )
    request_messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_RULE}\n"
                f"{search_policy}\n"
                "Thời gian hiện tại theo múi giờ máy chủ là "
                f"{datetime.now().astimezone().isoformat(timespec='seconds')}."
            ),
        },
        *messages,
    ]
    action_generation_started = perf_counter()
    result = generate_response(
        api_key,
        model,
        temperature,
        max_tokens,
        request_messages,
        json_mode=True,
    )
    action_generation_seconds = perf_counter() - action_generation_started
    action, action_value = _parse_assistant_action(result["content"], provider_name)
    system_data = None
    search_query = None
    search_action = None
    search_results = None
    search_timings = None
    search_cache_hit = None
    search_cache_cosine_score = None
    search_cached_query = None
    rag_total_seconds = None
    answer_generation_seconds = None

    if action == "search" and web_search_enabled:
        search_query = action_value
        search_action = result["content"]
        rag_started = perf_counter()
        search_response = semantic_search(
            query=search_query,
            max_results=max_web_pages,
            use_cross_encoder=use_cross_encoder,
            cache_lookup_enabled=cache_lookup_enabled,
            cache_write_enabled=cache_write_enabled,
            pre_rerank_count=pre_rerank_count,
            result_count=result_count,
        )
        rag_total_seconds = perf_counter() - rag_started
        search_results = search_response.get("results", [])[:result_count]
        search_timings = search_response.get("step_timings")
        search_cache_hit = search_response.get("cache_hit", False)
        search_cache_cosine_score = search_response.get("cache_cosine_score")
        search_cached_query = search_response.get("cached_query")
        system_data = _format_search_results(search_response, top_k=result_count)
        request_messages.extend(
            [
                {"role": "assistant", "content": result["content"]},
                {
                    "role": "user",
                    "content": (
                        f"Kết quả semantic search cho truy vấn '{search_query}':\n"
                        f"{system_data}\n\n"
                        "Hãy trả lời câu hỏi ban đầu dựa trên các nguồn này. "
                        "Không phát ra yêu cầu search lần nữa trong lượt trả lời này."
                    ),
                },
            ]
        )
        answer_generation_started = perf_counter()
        result = generate_response(
            api_key,
            model,
            temperature,
            max_tokens,
            request_messages,
        )
        answer_generation_seconds = perf_counter() - answer_generation_started
        message = result["content"]
    elif action == "search":
        request_messages.extend(
            [
                {"role": "assistant", "content": result["content"]},
                {
                    "role": "user",
                    "content": (
                        "Tìm kiếm web đã bị tắt. Không được tìm kiếm hay bịa nguồn. "
                        "Hãy trả lời câu hỏi ban đầu bằng kiến thức và ngữ cảnh hiện có "
                        "hoặc hỏi lại nếu cần làm rõ."
                    ),
                },
            ]
        )
        answer_generation_started = perf_counter()
        result = generate_response(
            api_key,
            model,
            temperature,
            max_tokens,
            request_messages,
        )
        answer_generation_seconds = perf_counter() - answer_generation_started
        message = result["content"]
    else:
        message = action_value

    chat_timings = {
        "action_generation_seconds": action_generation_seconds,
        "server_total_seconds": perf_counter() - request_started,
    }
    if rag_total_seconds is not None and answer_generation_seconds is not None:
        chat_timings["rag_total_seconds"] = rag_total_seconds
        chat_timings["answer_generation_seconds"] = answer_generation_seconds
    elif answer_generation_seconds is not None:
        chat_timings["answer_generation_seconds"] = answer_generation_seconds

    return {
        "message": message,
        "model": model,
        "usage": result["usage"],
        "chat_timings": chat_timings,
        "search_query": search_query,
        "search_action": search_action,
        "search_results": search_results,
        "search_timings": search_timings,
        "search_cache_hit": search_cache_hit,
        "search_cache_cosine_score": search_cache_cosine_score,
        "search_cached_query": search_cached_query,
        "system_data": system_data,
    }
