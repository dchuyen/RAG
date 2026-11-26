from functools import lru_cache
from typing import Literal

from fastapi import HTTPException

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
EmbeddingTextType = Literal["query", "passage"]


def is_e5_model(model_name: str) -> bool:
    return "e5" in model_name.casefold()


def prepare_embedding_text(
    text: str,
    model_name: str = DEFAULT_MODEL,
    text_type: EmbeddingTextType = "passage",
) -> str:
    cleaned_text = text.strip()
    if not cleaned_text or not is_e5_model(model_name):
        return cleaned_text

    lower_text = cleaned_text.casefold()
    if lower_text.startswith("query:") or lower_text.startswith("passage:"):
        return cleaned_text
    return f"{text_type}: {cleaned_text}"


@lru_cache(maxsize=3)
def get_embedding_model(model_name: str):
    """
    Tải và cache model SentenceTransformer trong memory để không bị load lại mỗi request.
    """
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể khởi tạo mô hình embedding '{model_name}': {str(exc)}",
        ) from exc


def preload_embedding_model(model_name: str = DEFAULT_MODEL):
    """
    Nạp trước mô hình embedding vào bộ nhớ cache khi khởi động server.
    """
    return get_embedding_model(model_name)


def encode_texts(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
    normalize: bool = True,
    text_type: EmbeddingTextType = "passage",
) -> list[list[float]]:
    cleaned_texts = [text.strip() for text in texts if text and text.strip()]
    if not cleaned_texts:
        raise HTTPException(
            status_code=422,
            detail="Danh sách văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )
    prepared_texts = [
        prepare_embedding_text(text, model_name, text_type) for text in cleaned_texts
    ]

    model = get_embedding_model(model_name)

    try:
        vectors = model.encode(
            prepared_texts,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi trong quá trình tính toán embedding: {exc}",
        ) from exc

    embeddings_list = (
        vectors.tolist() if hasattr(vectors, "tolist") else [list(vector) for vector in vectors]
    )
    if len(embeddings_list) != len(cleaned_texts):
        raise HTTPException(
            status_code=500,
            detail="Số lượng embedding trả về không khớp với số văn bản đầu vào.",
        )
    return embeddings_list


def encode_single_text(
    text: str,
    model_name: str = DEFAULT_MODEL,
    normalize: bool = True,
    text_type: EmbeddingTextType = "query",
) -> list[float]:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=422, detail="Văn bản không được để trống.")
    return encode_texts([cleaned_text], model_name, normalize, text_type)[0]
