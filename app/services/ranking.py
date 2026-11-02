import math
from typing import Any

from fastapi import HTTPException

from app.services.embeddings import DEFAULT_MODEL, encode_texts


def prepare_embedding_texts(
    query: str,
    documents: list[dict[str, Any]],
    model: str,
) -> list[str]:
    if "e5" in model.casefold():
        return [
            f"query: {query}",
            *(f"passage: {document['text'].strip()}" for document in documents),
        ]
    return [query, *(document["text"].strip() for document in documents)]


def rank_with_embeddings(
    query: str,
    model: str,
    documents: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> list[dict[str, Any]]:
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
            {
                "text": document["text"],
                "metadata": document["metadata"],
                "relevance_score": score,
            }
        )

    ranked.sort(key=lambda document: document["relevance_score"], reverse=True)
    return ranked


def rank_documents(
    query: str,
    documents: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    cleaned_query = query.strip()
    cleaned_documents = [
        {"text": document["text"], "metadata": document["metadata"]}
        for document in documents
        if document["text"].strip()
    ]
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if not cleaned_documents:
        raise HTTPException(
            status_code=422,
            detail="Danh sách văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )

    embeddings = encode_texts(
        prepare_embedding_texts(cleaned_query, cleaned_documents, model),
        model,
        normalize=True,
    )
    ranked = rank_with_embeddings(cleaned_query, model, cleaned_documents, embeddings)
    return {
        "query": cleaned_query,
        "model": model,
        "count": len(ranked),
        "results": ranked,
    }
