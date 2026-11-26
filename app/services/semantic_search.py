import re
from time import perf_counter
from typing import Any, Literal

from fastapi import HTTPException

from app.services.chunks import split_text
from app.services.embeddings import DEFAULT_MODEL
from app.services.query_cache import query_query_cache, store_query_cache
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT, rerank_documents
from app.services.scrape import scrape_webpage
from app.services.search import search_web
from app.services.markdown_export import sort_ranked_documents

CHROMA_MATCH_THRESHOLD = 0.9
_ISO_DATE_PATTERN = re.compile(r"\b(?:ngày\s+)?(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)


def _fallback_search_query(query: str) -> str | None:
    if "hôm nay" in query.casefold():
        return None

    match = _ISO_DATE_PATTERN.search(query)
    if match is None:
        return None
    return _ISO_DATE_PATTERN.sub(f"hôm nay {match.group(1)}", query, count=1)


def semantic_search(
    query: str,
    max_results: int = 10,
    region: str = "vn-vi",
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    model: str = DEFAULT_MODEL,
    use_cross_encoder: bool = True,
    cache_lookup_enabled: bool = False,
    cache_write_enabled: bool = False,
    pre_rerank_count: int = PRE_RERANK_COUNT,
    result_count: int = RESULT_COUNT,
) -> dict[str, Any]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap phải nhỏ hơn chunk_size.",
        )

    cache_lookup_started = perf_counter()
    cached_match = query_query_cache(
        query=cleaned_query,
        n_results=5,
        model=model,
        enabled=cache_lookup_enabled,
    )
    cache_lookup_seconds = perf_counter() - cache_lookup_started
    cache_cosine_score = (
        cached_match["relevance_score"]
        if cache_lookup_enabled and cached_match is not None
        else None
    )
    cached_query = (
        cached_match["cached_response"].get("query")
        if cache_lookup_enabled and cached_match is not None
        else None
    )
    if (
        cache_lookup_enabled
        and cached_match is not None
        and cached_match["relevance_score"] >= CHROMA_MATCH_THRESHOLD
        and cached_match["cached_response"].get("use_cross_encoder") == use_cross_encoder
        and cached_match["cached_response"].get("pre_rerank_count") == pre_rerank_count
        and cached_match["cached_response"].get("result_count") == result_count
    ):
        cached_response = cached_match["cached_response"].copy()
        cached_response["query"] = cleaned_query
        cached_response["model"] = model
        cached_response["cache_hit"] = True
        cached_response["searched_url_count"] = 0
        cached_response["scraped_page_count"] = 0
        cached_response["total_chunks"] = len(cached_response.get("results", []))
        cached_response["failed_pages"] = []
        cached_response["cache_cosine_score"] = cache_cosine_score
        cached_response["cached_query"] = cached_query
        cached_response["step_timings"] = {
            "cache_lookup_seconds": cache_lookup_seconds,
            "search_seconds": 0.0,
            "scrape_seconds": 0.0,
            "chunk_seconds": 0.0,
            "ranking_seconds": 0.0,
        }
        return cached_response

    search_queries = [cleaned_query]
    fallback_query = _fallback_search_query(cleaned_query)
    if fallback_query is not None and fallback_query != cleaned_query:
        search_queries.append(fallback_query)
    documents: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    searched_urls: set[str] = set()
    scraped_page_count = 0
    search_seconds = 0.0
    scrape_seconds = 0.0
    chunk_seconds = 0.0

    for search_query in search_queries:
        search_started = perf_counter()
        urls = search_web(
            q=search_query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
        )
        search_seconds += perf_counter() - search_started

        for url in urls:
            if url in searched_urls:
                continue
            searched_urls.add(url)
            scrape_started = perf_counter()
            try:
                scraped_page = scrape_webpage(url=url)
            except HTTPException as exc:
                failed_pages.append(
                    {"url": url, "status_code": exc.status_code, "detail": exc.detail}
                )
                continue
            finally:
                scrape_seconds += perf_counter() - scrape_started

            text = scraped_page.get("text")
            if not isinstance(text, str) or not text.strip():
                failed_pages.append(
                    {
                        "url": url,
                        "status_code": 422,
                        "detail": "Không trích xuất được nội dung văn bản từ trang.",
                    }
                )
                continue

            scraped_page_count += 1
            metadata = {
                key: value for key, value in scraped_page.items() if key != "text"
            }
            metadata.setdefault("source", url)
            chunk_started = perf_counter()
            chunks = split_text(
                text=text,
                metadata=metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            chunk_seconds += perf_counter() - chunk_started
            documents.extend(chunks)
        if documents:
            break

    if not documents:
        return {
            "query": cleaned_query,
            "model": model,
            "searched_url_count": len(searched_urls),
            "scraped_page_count": scraped_page_count,
            "total_chunks": 0,
            "cache_hit": False,
            "cache_cosine_score": cache_cosine_score,
            "cached_query": cached_query,
            "failed_pages": failed_pages,
            "results": [],
            "step_timings": {
                "cache_lookup_seconds": cache_lookup_seconds,
                "search_seconds": search_seconds,
                "scrape_seconds": scrape_seconds,
                "chunk_seconds": chunk_seconds,
                "ranking_seconds": 0.0,
            },
        }

    ranking_started = perf_counter()
    ranked = sort_ranked_documents(
        rerank_documents(
            cleaned_query,
            documents,
            use_cross_encoder=use_cross_encoder,
            pre_rerank_count=pre_rerank_count,
            result_count=result_count,
        )
    )
    ranking_seconds = perf_counter() - ranking_started

    response = {
        "query": cleaned_query,
        "model": model,
        "use_cross_encoder": use_cross_encoder,
        "pre_rerank_count": pre_rerank_count,
        "result_count": result_count,
        "cache_hit": False,
        "cache_cosine_score": cache_cosine_score,
        "cached_query": cached_query,
        "searched_url_count": len(searched_urls),
        "scraped_page_count": scraped_page_count,
        "total_chunks": len(documents),
        "failed_pages": failed_pages,
        "results": ranked,
        "step_timings": {
            "cache_lookup_seconds": cache_lookup_seconds,
            "search_seconds": search_seconds,
            "scrape_seconds": scrape_seconds,
            "chunk_seconds": chunk_seconds,
            "ranking_seconds": ranking_seconds,
        },
    }
    store_query_cache(
        cleaned_query,
        response,
        model=model,
        enabled=cache_write_enabled,
    )
    return response
