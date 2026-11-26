from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.embeddings import DEFAULT_MODEL, encode_single_text, encode_texts
from app.services.ranking import PRE_RERANK_COUNT, RESULT_COUNT, rank_documents

router = APIRouter()


class EmbeddingsRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str = DEFAULT_MODEL
    normalize: bool = True
    text_type: Literal["query", "passage"] = "passage"


class RankingDocument(BaseModel):
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankingRequest(BaseModel):
    query: str = Field(min_length=1)
    documents: list[RankingDocument] = Field(min_length=1)
    model: str = DEFAULT_MODEL
    pre_rerank_count: int = Field(default=PRE_RERANK_COUNT, ge=1, le=50)
    result_count: int = Field(default=RESULT_COUNT, ge=1, le=50)


@router.post("/embeddings")
def create_embeddings(request: EmbeddingsRequest) -> dict[str, Any]:
    embeddings = encode_texts(
        request.texts,
        model_name=request.model,
        normalize=request.normalize,
        text_type=request.text_type,
    )
    return {
        "model": request.model,
        "count": len(embeddings),
        "embeddings": embeddings,
    }


@router.get("/embeddings/single")
def create_single_embedding(
    text: str = Query(min_length=1),
    model: str = DEFAULT_MODEL,
    text_type: Literal["query", "passage"] = "query",
) -> dict[str, Any]:
    return {
        "model": model,
        "embedding": encode_single_text(text, model, text_type=text_type),
    }


@router.post("/ranking")
def rank_documents_endpoint(request: RankingRequest) -> dict[str, Any]:
    return rank_documents(
        query=request.query,
        documents=[document.model_dump() for document in request.documents],
        model=request.model,
        pre_rerank_count=request.pre_rerank_count,
        result_count=request.result_count,
    )
