from time import perf_counter
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.routers.chunks import ChunkRequest, split_into_chunks
from app.routers.embeddings import DEFAULT_MODEL, EmbedRequest, create_embeddings
from app.routers.ranking import (
    RankingDocument,
    RankedDocument,
    prepare_embedding_texts,
    rank_with_embeddings,
)
from app.routers.scrape import scrape_webpage
from app.routers.search import search_web

router = APIRouter(prefix="/semantic-search", tags=["semantic-search"])


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Nội dung tìm kiếm.")
    max_results: int = Field(default=1, ge=1, le=50)
    region: str = Field(default="wt-wt")
    safesearch: Literal["off", "moderate", "strict"] = "moderate"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)


class ScrapeFailure(BaseModel):
    url: str
    status_code: int
    detail: Any


class StepTimings(BaseModel):
    search_seconds: float
    scrape_seconds: float
    chunk_seconds: float
    embedding_seconds: float
    ranking_seconds: float


class SemanticSearchResponse(BaseModel):
    query: str
    model: str
    searched_url_count: int
    scraped_page_count: int
    total_chunks: int
    failed_pages: list[ScrapeFailure]
    results: list[RankedDocument]
    step_timings: StepTimings


@router.post("", response_model=SemanticSearchResponse)
def semantic_search(payload: SemanticSearchRequest) -> SemanticSearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if payload.chunk_overlap >= payload.chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap phải nhỏ hơn chunk_size.",
        )

    search_started = perf_counter()
    urls = search_web(
        q=query,
        max_results=payload.max_results,
        region=payload.region,
        safesearch=payload.safesearch,
    )
    search_seconds = perf_counter() - search_started

    documents: list[RankingDocument] = []
    failed_pages: list[ScrapeFailure] = []
    scraped_page_count = 0
    scrape_seconds = 0.0
    chunk_seconds = 0.0

    for url in urls:
        scrape_started = perf_counter()
        try:
            scraped_page = scrape_webpage(url=url)
        except HTTPException as exc:
            failed_pages.append(
                ScrapeFailure(url=url, status_code=exc.status_code, detail=exc.detail)
            )
            continue
        finally:
            scrape_seconds += perf_counter() - scrape_started

        text = scraped_page.get("text")
        if not isinstance(text, str) or not text.strip():
            failed_pages.append(
                ScrapeFailure(
                    url=url,
                    status_code=422,
                    detail="Không trích xuất được nội dung văn bản từ trang.",
                )
            )
            continue

        scraped_page_count += 1
        metadata = {key: value for key, value in scraped_page.items() if key != "text"}
        metadata.setdefault("source", url)
        chunk_started = perf_counter()
        chunk_response = split_into_chunks(
            ChunkRequest(
                text=text,
                metadata=metadata,
                chunk_size=payload.chunk_size,
                chunk_overlap=payload.chunk_overlap,
            )
        )
        chunk_seconds += perf_counter() - chunk_started
        documents.extend(
            RankingDocument(text=chunk.text, metadata=chunk.metadata)
            for chunk in chunk_response.chunks
        )

    if not documents:
        return SemanticSearchResponse(
            query=query,
            model=payload.model,
            searched_url_count=len(urls),
            scraped_page_count=scraped_page_count,
            total_chunks=0,
            failed_pages=failed_pages,
            results=[],
            step_timings=StepTimings(
                search_seconds=search_seconds,
                scrape_seconds=scrape_seconds,
                chunk_seconds=chunk_seconds,
                embedding_seconds=0.0,
                ranking_seconds=0.0,
            ),
        )

    embedding_started = perf_counter()
    embedding_response = create_embeddings(
        EmbedRequest(
            texts=prepare_embedding_texts(query, documents, payload.model),
            model=payload.model,
            normalize=True,
        )
    )
    embedding_seconds = perf_counter() - embedding_started
    ranking_started = perf_counter()
    ranking_response = rank_with_embeddings(
        query=query,
        model=payload.model,
        documents=documents,
        embeddings=embedding_response.embeddings,
    )
    ranking_seconds = perf_counter() - ranking_started

    return SemanticSearchResponse(
        query=query,
        model=ranking_response.model,
        searched_url_count=len(urls),
        scraped_page_count=scraped_page_count,
        total_chunks=len(documents),
        failed_pages=failed_pages,
        results=ranking_response.results,
        step_timings=StepTimings(
            search_seconds=search_seconds,
            scrape_seconds=scrape_seconds,
            chunk_seconds=chunk_seconds,
            embedding_seconds=embedding_seconds,
            ranking_seconds=ranking_seconds,
        ),
    )
