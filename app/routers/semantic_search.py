from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.routers.ranking import RankedDocument
from app.services.embeddings import DEFAULT_MODEL
from app.services.semantic_search import semantic_search as run_semantic_search

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
    response = run_semantic_search(
        query=payload.query,
        max_results=payload.max_results,
        region=payload.region,
        safesearch=payload.safesearch,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        model=payload.model,
    )
    return SemanticSearchResponse(**response)
