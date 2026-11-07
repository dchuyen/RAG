from time import perf_counter
from typing import Any, Literal

from fastapi import HTTPException

from app.services.chunks import split_text
from app.services.embeddings import DEFAULT_MODEL, encode_texts
from app.services.ranking import prepare_embedding_texts, rank_with_embeddings
from app.services.scrape import scrape_webpage
from app.services.search import search_web
from app.services.source_merge import merge_ranked_documents_by_source


def semantic_search(
    query: str,
    max_results: int = 3,
    region: str = "wt-wt",
    safesearch: Literal["off", "moderate", "strict"] = "moderate",
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap phải nhỏ hơn chunk_size.",
        )

    search_started = perf_counter()
    urls = search_web(
        q=cleaned_query,
        max_results=max_results,
        region=region,
        safesearch=safesearch,
    )
    search_seconds = perf_counter() - search_started

    documents: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    scraped_page_count = 0
    scrape_seconds = 0.0
    chunk_seconds = 0.0

    for url in urls:
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
        metadata = {key: value for key, value in scraped_page.items() if key != "text"}
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

    if not documents:
        return {
            "query": cleaned_query,
            "model": model,
            "searched_url_count": len(urls),
            "scraped_page_count": scraped_page_count,
            "total_chunks": 0,
            "failed_pages": failed_pages,
            "results": [],
            "step_timings": {
                "search_seconds": search_seconds,
                "scrape_seconds": scrape_seconds,
                "chunk_seconds": chunk_seconds,
                "embedding_seconds": 0.0,
                "ranking_seconds": 0.0,
            },
        }

    embedding_started = perf_counter()
    embeddings = encode_texts(
        prepare_embedding_texts(cleaned_query, documents, model),
        model,
        normalize=True,
    )
    embedding_seconds = perf_counter() - embedding_started
    ranking_started = perf_counter()
    ranked = merge_ranked_documents_by_source(
        rank_with_embeddings(cleaned_query, model, documents, embeddings)
    )
    ranking_seconds = perf_counter() - ranking_started

    return {
        "query": cleaned_query,
        "model": model,
        "searched_url_count": len(urls),
        "scraped_page_count": scraped_page_count,
        "total_chunks": len(documents),
        "failed_pages": failed_pages,
        "results": ranked,
        "step_timings": {
            "search_seconds": search_seconds,
            "scrape_seconds": scrape_seconds,
            "chunk_seconds": chunk_seconds,
            "embedding_seconds": embedding_seconds,
            "ranking_seconds": ranking_seconds,
        },
    }
