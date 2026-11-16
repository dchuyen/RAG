from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.embeddings import DEFAULT_MODEL, encode_single_text, encode_texts
from app.services.ranking import rank_documents

router = APIRouter()


class EmbeddingsRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str = DEFAULT_MODEL
    normalize: bool = True


class RankingDocument(BaseModel):
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankingRequest(BaseModel):
    query: str = Field(min_length=1)
    documents: list[RankingDocument] = Field(min_length=1)
    model: str = DEFAULT_MODEL


@router.post("/embeddings")
def create_embeddings(request: EmbeddingsRequest) -> dict[str, Any]:
    embeddings = encode_texts(
        request.texts,
        model_name=request.model,
        normalize=request.normalize,
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
) -> dict[str, Any]:
    return {
        "model": model,
        "embedding": encode_single_text(text, model),
    }


@router.post("/ranking")
def rank_documents_endpoint(request: RankingRequest) -> dict[str, Any]:
    return rank_documents(
        query=request.query,
        documents=[document.model_dump() for document in request.documents],
        model=request.model,
    )
