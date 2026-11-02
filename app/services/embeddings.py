from functools import lru_cache

from fastapi import HTTPException

DEFAULT_MODEL = "intfloat/multilingual-e5-small"


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


def encode_texts(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
    normalize: bool = True,
) -> list[list[float]]:
    cleaned_texts = [text.strip() for text in texts if text and text.strip()]
    if not cleaned_texts:
        raise HTTPException(
            status_code=422,
            detail="Danh sách văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )

    model = get_embedding_model(model_name)

    try:
        vectors = model.encode(
            cleaned_texts,
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
) -> list[float]:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=422, detail="Văn bản không được để trống.")
    return encode_texts([cleaned_text], model_name, normalize)[0]
