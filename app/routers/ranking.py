from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ranking import (
    DEFAULT_MODEL,
    prepare_embedding_texts,
    rank_documents as run_ranking,
    rank_with_embeddings,
)

router = APIRouter(prefix="/ranking", tags=["ranking"])


class RankingDocument(BaseModel):
    text: str = Field(..., min_length=1, description="Nội dung văn bản cần xếp hạng.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankingRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Nội dung tìm kiếm.")
    documents: list[RankingDocument] = Field(
        ...,
        min_length=1,
        description="Danh sách văn bản cần so khớp với nội dung tìm kiếm.",
    )
    model: str = Field(default=DEFAULT_MODEL, description="Tên mô hình embedding.")


class RankedDocument(RankingDocument):
    relevance_score: float


class RankingResponse(BaseModel):
    query: str
    model: str
    count: int
    results: list[RankedDocument]


@router.post("", response_model=RankingResponse)
def rank_documents(payload: RankingRequest) -> RankingResponse:
    response = run_ranking(
        payload.query,
        [document.model_dump() for document in payload.documents],
        payload.model,
    )
    return RankingResponse(**response)
