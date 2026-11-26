import asyncio
import hashlib
import json
import math
import os
import time
from functools import lru_cache
from typing import Any

import chromadb
from fastapi import HTTPException

from app.services.chroma import CHROMA_DB_PATH
from app.services.embeddings import DEFAULT_MODEL, encode_texts
from app.services.ranking import _cross_encoder_scores

CHROMA_QUERY_CACHE_COLLECTION_NAME = os.getenv(
    "CHROMA_QUERY_CACHE_COLLECTION_NAME",
    "semantic_query_cache",
)
CACHE_TTL_SECONDS = 5 * 60
CACHE_CLEANUP_INTERVAL_SECONDS = 30
QUERY_CACHE_LOOKUP_ENABLED = True
QUERY_CACHE_WRITE_ENABLED = True


@lru_cache(maxsize=1)
def _get_query_cache_collection() -> Any:
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    return client.get_or_create_collection(
        name=CHROMA_QUERY_CACHE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


def store_query_cache(
    query: str,
    response: dict[str, Any],
    model: str = DEFAULT_MODEL,
    enabled: bool = False,
) -> None:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Truy vấn cache không được để trống.")
    if not enabled or not QUERY_CACHE_WRITE_ENABLED:
        return

    query_embedding = encode_texts(
        [cleaned_query],
        model,
        normalize=True,
        text_type="query",
    )[0]
    cache_id = hashlib.sha256(
        f"{model}\0{cleaned_query}".encode("utf-8")
    ).hexdigest()
    payload = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    _get_query_cache_collection().upsert(
        ids=[cache_id],
        documents=[payload],
        metadatas=[
            {
                "model": model,
                "query": cleaned_query,
                "expires_at": time.time() + CACHE_TTL_SECONDS,
            }
        ],
        embeddings=[query_embedding],
    )


def query_query_cache(
    query: str,
    n_results: int = 5,
    model: str = DEFAULT_MODEL,
    enabled: bool = False,
) -> dict[str, Any] | None:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if isinstance(n_results, bool) or not isinstance(n_results, int) or n_results < 1:
        raise HTTPException(status_code=422, detail="n_results phải lớn hơn 0.")
    if not enabled or not QUERY_CACHE_LOOKUP_ENABLED:
        return None

    records = _get_query_cache_collection().get(
        where={
            "$and": [
                {"model": model},
                {"expires_at": {"$gt": time.time()}},
            ]
        },
        include=["documents", "metadatas"],
    )

    candidates: list[tuple[str, dict[str, Any]]] = []
    for payload, metadata in zip(records["documents"], records["metadatas"]):
        if not isinstance(payload, str):
            continue
        try:
            cached_response = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(cached_response, dict):
            continue

        cached_query = metadata.get("query") if isinstance(metadata, dict) else None
        if not isinstance(cached_query, str) or not cached_query.strip():
            cached_query = cached_response.get("query")
        if isinstance(cached_query, str) and cached_query.strip():
            candidates.append((cached_query, cached_response))

    if not candidates:
        return None

    scores = _cross_encoder_scores(
        cleaned_query,
        [{"text": cached_query} for cached_query, _ in candidates],
    )
    best_index = max(range(len(scores)), key=scores.__getitem__)
    cross_encoder_score = scores[best_index]
    if cross_encoder_score >= 0:
        relevance_score = 1 / (1 + math.exp(-cross_encoder_score))
    else:
        exponential_score = math.exp(cross_encoder_score)
        relevance_score = exponential_score / (1 + exponential_score)

    return {
        "cached_response": candidates[best_index][1],
        "relevance_score": relevance_score,
    }


def cleanup_expired_query_cache() -> int:
    collection = _get_query_cache_collection()
    records = collection.get(include=["metadatas"])
    now = time.time()
    expired_ids = [
        cache_id
        for cache_id, metadata in zip(records["ids"], records["metadatas"])
        if not metadata
        or not isinstance(metadata.get("expires_at"), (int, float))
        or metadata["expires_at"] <= now
    ]
    if expired_ids:
        collection.delete(ids=expired_ids)
    return len(expired_ids)


async def run_query_cache_cleanup() -> None:
    while True:
        await asyncio.to_thread(cleanup_expired_query_cache)
        await asyncio.sleep(CACHE_CLEANUP_INTERVAL_SECONDS)
