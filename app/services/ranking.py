import math
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from fastapi import HTTPException

from app.services.embeddings import (
    DEFAULT_MODEL,
    prepare_embedding_text,
)

CROSS_ENCODER_MODEL = "Horizon-Labs/multilingual-reranker-small"
PRE_RERANK_COUNT = 5
RESULT_COUNT = 3
_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DMY_DATE_PATTERN = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_VIETNAMESE_DATE_PATTERN = re.compile(
    r"\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})\b",
    re.IGNORECASE,
)
_DATE_RANGE_START_PATTERN = re.compile(
    r"\b(\d{1,2})/(\d{1,2})\s*[–-]\s*\d{1,2}/\d{1,2}/(\d{4})\b"
)


def prepare_embedding_texts(
    query: str,
    documents: list[dict[str, Any]],
    model: str,
) -> list[str]:
    if "e5" in model.casefold():
        return [
            prepare_embedding_text(query, model, "query"),
            *(
                prepare_embedding_text(document["text"], model, "passage")
                for document in documents
            ),
        ]
    return [query, *(document["text"].strip() for document in documents)]


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _bm25_scores(query: str, documents: list[dict[str, Any]]) -> list[float]:
    query_tokens = _tokenize(query)
    tokenized_documents = [_tokenize(document["text"]) for document in documents]
    if not query_tokens or not tokenized_documents:
        return [0.0] * len(documents)

    document_frequencies: dict[str, int] = {}
    for tokens in tokenized_documents:
        for token in set(tokens):
            document_frequencies[token] = document_frequencies.get(token, 0) + 1

    document_count = len(tokenized_documents)
    average_length = sum(map(len, tokenized_documents)) / document_count
    scores: list[float] = []
    for tokens in tokenized_documents:
        frequencies: dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1

        score = 0.0
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            document_frequency = document_frequencies[token]
            inverse_document_frequency = math.log(
                1 + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            length_normalization = frequency + 1.5 * (
                1 - 0.75 + 0.75 * len(tokens) / max(average_length, 1)
            )
            score += (
                inverse_document_frequency
                * frequency
                * 2.5
                / length_normalization
            )
        scores.append(score)

    maximum = max(scores, default=0.0)
    if maximum <= 0:
        return [0.0] * len(scores)
    return [score / maximum for score in scores]


def _extract_dates(text: str) -> list[date]:
    dates: list[date] = []
    for pattern, order in (
        (_ISO_DATE_PATTERN, "ymd"),
        (_DMY_DATE_PATTERN, "dmy"),
        (_VIETNAMESE_DATE_PATTERN, "dmy"),
    ):
        for match in pattern.finditer(text):
            first, second, third = map(int, match.groups())
            year, month, day = (
                (first, second, third) if order == "ymd" else (third, second, first)
            )
            try:
                dates.append(date(year, month, day))
            except ValueError:
                continue

    for match in _DATE_RANGE_START_PATTERN.finditer(text):
        day, month, year = map(int, match.groups())
        try:
            dates.append(date(year, month, day))
        except ValueError:
            continue
    return dates


def _date_proximity_scores(
    query: str,
    documents: list[dict[str, Any]],
) -> list[float]:
    query_dates = _extract_dates(query)
    target_date = query_dates[0] if query_dates else datetime.now().date()
    scores: list[float] = []

    for document in documents:
        metadata = document.get("metadata", {})
        metadata_date = metadata.get("date") if isinstance(metadata, dict) else None
        dates = _extract_dates(document["text"])
        if isinstance(metadata_date, str):
            dates.extend(_extract_dates(metadata_date))
        if not dates:
            scores.append(0.5)
            continue

        nearest_days = min(abs((document_date - target_date).days) for document_date in dates)
        scores.append(1 / (1 + nearest_days / 30))
    return scores


@lru_cache(maxsize=1)
def _get_cross_encoder() -> Any:
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(CROSS_ENCODER_MODEL, max_length=512)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Không thể khởi tạo mô hình xếp hạng "
                f"'{CROSS_ENCODER_MODEL}': {exc}"
            ),
        ) from exc


def preload_cross_encoder() -> Any:
    """
    Nạp trước mô hình cross-encoder vào bộ nhớ cache khi khởi động server.
    """
    return _get_cross_encoder()


def _cross_encoder_scores(query: str, documents: list[dict[str, Any]]) -> list[float]:
    try:
        predictions = _get_cross_encoder().predict(
            [(query, document["text"]) for document in documents],
            batch_size=16,
            show_progress_bar=False,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xếp hạng lại bằng cross-encoder: {exc}",
        ) from exc

    scores = [float(score) for score in predictions]
    if len(scores) != len(documents):
        raise HTTPException(
            status_code=500,
            detail="Số điểm cross-encoder không khớp với số văn bản.",
        )
    return scores


def rerank_documents(
    query: str,
    documents: list[dict[str, Any]],
    use_cross_encoder: bool = True,
    pre_rerank_count: int = PRE_RERANK_COUNT,
    result_count: int = RESULT_COUNT,
) -> list[dict[str, Any]]:
    bm25_scores = _bm25_scores(query, documents)
    date_scores = _date_proximity_scores(query, documents)
    preliminarily_ranked = []
    for document, bm25_score, date_score in zip(documents, bm25_scores, date_scores):
        preliminarily_ranked.append(
            {
                "text": document["text"],
                "metadata": document["metadata"],
                "bm25_score": bm25_score,
                "date_score": date_score,
            }
        )

    preliminarily_ranked.sort(
        key=lambda document: (
            0.8 * document["bm25_score"] + 0.2 * document["date_score"]
        ),
        reverse=True,
    )
    reranking_documents = preliminarily_ranked[:pre_rerank_count]
    if not use_cross_encoder:
        ranked = [
            {
                **document,
                "relevance_score": (
                    0.8 * document["bm25_score"]
                    + 0.2 * document["date_score"]
                ),
                "cross_encoder_score": None,
            }
            for document in reranking_documents
        ]
        ranked.sort(key=lambda document: document["relevance_score"], reverse=True)
        return ranked[:result_count]

    cross_encoder_scores = _cross_encoder_scores(query, reranking_documents)
    ranked = []

    for document, cross_encoder_score in zip(
        reranking_documents,
        cross_encoder_scores,
    ):
        if cross_encoder_score >= 0:
            normalized_cross_encoder_score = 1 / (
                1 + math.exp(-cross_encoder_score)
            )
        else:
            exponential_score = math.exp(cross_encoder_score)
            normalized_cross_encoder_score = exponential_score / (
                1 + exponential_score
            )
        ranked.append(
            {
                **document,
                "relevance_score": normalized_cross_encoder_score,
                "cross_encoder_score": cross_encoder_score,
            }
        )

    ranked.sort(key=lambda document: document["relevance_score"], reverse=True)
    return ranked[:result_count]


def rank_documents(
    query: str,
    documents: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    use_cross_encoder: bool = True,
    pre_rerank_count: int = PRE_RERANK_COUNT,
    result_count: int = RESULT_COUNT,
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

    ranked = rerank_documents(
        cleaned_query,
        cleaned_documents,
        use_cross_encoder=use_cross_encoder,
        pre_rerank_count=pre_rerank_count,
        result_count=result_count,
    )
    return {
        "query": cleaned_query,
        "model": model,
        "count": len(ranked),
        "results": ranked,
    }
