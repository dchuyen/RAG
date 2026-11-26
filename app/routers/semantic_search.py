from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.embeddings import DEFAULT_MODEL
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT
from app.services.semantic_search import semantic_search as run_semantic_search

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=10, ge=1, le=50)
    region: str = "vn-vi"
    safesearch: Literal["off", "moderate", "strict"] = "moderate"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)
    model: str = DEFAULT_MODEL
    use_cross_encoder: bool = True
    cache_lookup_enabled: bool = False
    cache_write_enabled: bool = False
    pre_rerank_count: int = Field(default=PRE_RERANK_COUNT, ge=1, le=50)
    result_count: int = Field(default=RESULT_COUNT, ge=1, le=50)


@router.post("/semantic-search")
def semantic_search_endpoint(request: SemanticSearchRequest) -> dict[str, Any]:
    return run_semantic_search(**request.model_dump())
