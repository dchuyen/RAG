import hashlib
import json
import math
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from fastapi import HTTPException

from app.services.embeddings import DEFAULT_MODEL, encode_texts
from app.services.ranking import prepare_embedding_texts

load_dotenv()

CHROMA_DB_PATH = Path(
    os.getenv(
        "CHROMA_DB_PATH",
        str(Path(__file__).resolve().parents[2] / "data" / "chroma"),
    )
).expanduser()
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "documents")


@lru_cache(maxsize=1)
def _get_collection() -> Any:
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


def _clean_documents(
    documents: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, str | int | float | bool]]]:
    if not documents:
        raise HTTPException(status_code=422, detail="Danh sách tài liệu không được để trống.")

    texts: list[str] = []
    metadatas: list[dict[str, str | int | float | bool]] = []
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Tài liệu {index} phải là object.",
            )
        text = document.get("text")
        metadata = document.get("metadata", {})
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(
                status_code=422,
                detail=f"Trường 'text' của tài liệu {index} phải là chuỗi không rỗng.",
            )
        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Trường 'metadata' của tài liệu {index} phải là object.",
            )
        if any(
            not isinstance(key, str)
            or not isinstance(value, (str, int, float, bool))
            or (isinstance(value, float) and not math.isfinite(value))
            for key, value in metadata.items()
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Metadata của tài liệu {index} chỉ được chứa giá trị "
                    "chuỗi, số hữu hạn hoặc boolean."
                ),
            )

        texts.append(text.strip())
        metadatas.append(metadata.copy())

    return texts, metadatas


def _document_ids(
    texts: list[str],
    metadatas: list[dict[str, str | int | float | bool]],
) -> list[str]:
    occurrences: defaultdict[str, int] = defaultdict(int)
    ids = []
    for text, metadata in zip(texts, metadatas):
        serialized = json.dumps(
            [text, metadata],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        document_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        occurrence = occurrences[document_hash]
        occurrences[document_hash] += 1
        ids.append(f"{document_hash}-{occurrence}")
    return ids


def store_documents(
    documents: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    embeddings: list[list[float]] | None = None,
) -> dict[str, int]:
    texts, metadatas = _clean_documents(documents)
    if embeddings is None:
        embedding_texts = prepare_embedding_texts(
            "", [{"text": text} for text in texts], model
        )[1:]
        embeddings = encode_texts(embedding_texts, model, normalize=True)
    elif len(embeddings) != len(texts):
        raise HTTPException(
            status_code=500,
            detail="Số embedding không khớp với số tài liệu cần lưu vào ChromaDB.",
        )

    ids = _document_ids(texts, metadatas)
    collection = _get_collection()
    documents_with_metadata = [
        index for index, metadata in enumerate(metadatas) if metadata
    ]
    documents_without_metadata = [
        index for index, metadata in enumerate(metadatas) if not metadata
    ]
    if documents_with_metadata:
        collection.upsert(
            ids=[ids[index] for index in documents_with_metadata],
            documents=[texts[index] for index in documents_with_metadata],
            metadatas=[metadatas[index] for index in documents_with_metadata],
            embeddings=[embeddings[index] for index in documents_with_metadata],
        )
    if documents_without_metadata:
        collection.upsert(
            ids=[ids[index] for index in documents_without_metadata],
            documents=[texts[index] for index in documents_without_metadata],
            embeddings=[embeddings[index] for index in documents_without_metadata],
        )
    return {"stored_count": len(texts)}


def query_documents(
    query: str,
    n_results: int = 5,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    cleaned_query = query.strip()
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="Nội dung tìm kiếm không được để trống.")
    if isinstance(n_results, bool) or not isinstance(n_results, int) or n_results < 1:
        raise HTTPException(status_code=422, detail="n_results phải lớn hơn 0.")

    query_embedding_text = prepare_embedding_texts(cleaned_query, [], model)[0]
    query_embedding = encode_texts([query_embedding_text], model, normalize=True)[0]
    result = _get_collection().query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    result_texts = result["documents"][0]
    result_metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    results = [
        {
            "text": text,
            "metadata": metadata or {},
            "relevance_score": 1 - distance,
        }
        for text, metadata, distance in zip(result_texts, result_metadatas, distances)
        if text is not None and distance is not None
    ]
    return {
        "query": cleaned_query,
        "count": len(results),
        "results": results,
    }
