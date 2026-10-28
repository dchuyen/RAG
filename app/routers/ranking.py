import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.routers.embeddings import DEFAULT_MODEL, encode_texts

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


def prepare_embedding_texts(
    query: str,
    documents: list[RankingDocument],
    model: str,
) -> list[str]:
    if "e5" in model.casefold():
        return [
            f"query: {query}",
            *(f"passage: {document.text.strip()}" for document in documents),
        ]
    return [query, *(document.text.strip() for document in documents)]


def rank_with_embeddings(
    query: str,
    model: str,
    documents: list[RankingDocument],
    embeddings: list[list[float]],
) -> RankingResponse:
    if len(embeddings) != len(documents) + 1:
        raise HTTPException(
            status_code=500,
            detail="Số embedding không khớp với truy vấn và danh sách văn bản.",
        )

    query_embedding = embeddings[0]
    ranked = []
    for document, document_embedding in zip(documents, embeddings[1:]):
        if len(document_embedding) != len(query_embedding):
            raise HTTPException(
                status_code=500,
                detail="Embedding truy vấn và văn bản không cùng số chiều.",
            )
        score = math.fsum(
            query_value * document_value
            for query_value, document_value in zip(query_embedding, document_embedding)
        )
        ranked.append(
            RankedDocument(
                text=document.text,
                metadata=document.metadata,
                relevance_score=score,
            )
        )

    ranked.sort(key=lambda document: document.relevance_score, reverse=True)
    return RankingResponse(
        query=query,
        model=model,
        count=len(ranked),
        results=ranked,
    )


@router.post("", response_model=RankingResponse)
def rank_documents(payload: RankingRequest) -> RankingResponse:
    query = payload.query.strip()
    documents = [document for document in payload.documents if document.text.strip()]
    if not query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if not documents:
        raise HTTPException(
            status_code=422,
            detail="Danh sách văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )

    embeddings = encode_texts(
        prepare_embedding_texts(query, documents, payload.model),
        payload.model,
        normalize=True,
    )
    return rank_with_embeddings(query, payload.model, documents, embeddings)
