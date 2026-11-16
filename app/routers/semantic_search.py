from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.embeddings import DEFAULT_MODEL
from app.services.semantic_search import semantic_search as run_semantic_search

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=50)
    region: str = "vn-vi"
    safesearch: Literal["off", "moderate", "strict"] = "moderate"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)
    model: str = DEFAULT_MODEL


@router.post("/semantic-search")
def semantic_search_endpoint(request: SemanticSearchRequest) -> dict[str, Any]:
    return run_semantic_search(**request.model_dump())
