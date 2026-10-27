from functools import lru_cache
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class EmbedRequest(BaseModel):
    texts: list[str] = Field(
        ...,
        min_length=1,
        description="Danh sách các đoạn văn bản cần tạo embedding.",
        examples=[["Xin chào, đây là văn bản tiếng Việt.", "Hệ thống truy xuất thông tin tự động."]],
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Tên mô hình embedding trên HuggingFace (mặc định intfloat/multilingual-e5-small).",
    )
    normalize: bool = Field(
        default=True,
        description="Chuẩn hoá vector (L2 norm) phục vụ tính Cosine Similarity bằng dot product.",
    )


class EmbedResponse(BaseModel):
    model: str
    dimension: int
    count: int
    embeddings: list[list[float]]


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


@router.post("", response_model=EmbedResponse)
def create_embeddings(payload: EmbedRequest) -> EmbedResponse:
    """
    Tạo embedding vector cho danh sách văn bản.
    """
    cleaned_texts = [text.strip() for text in payload.texts if text and text.strip()]
    if not cleaned_texts:
        raise HTTPException(
            status_code=422,
            detail="Danh sách văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )

    model = get_embedding_model(payload.model)

    try:
        vectors = model.encode(
            cleaned_texts,
            normalize_embeddings=payload.normalize,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi trong quá trình tính toán embedding: {str(exc)}",
        ) from exc

    embeddings_list = vectors.tolist() if hasattr(vectors, "tolist") else [list(v) for v in vectors]
    dim = len(embeddings_list[0]) if embeddings_list else 0

    return EmbedResponse(
        model=payload.model,
        dimension=dim,
        count=len(embeddings_list),
        embeddings=embeddings_list,
    )


@router.get("/single")
def create_single_embedding(
    text: str = Query(..., min_length=1, description="Văn bản cần embedding"),
    model: str = Query(default=DEFAULT_MODEL, description="Tên mô hình embedding"),
    normalize: bool = Query(default=True, description="Chuẩn hoá L2 norm"),
) -> dict:
    """
    Endpoint GET tiện lợi để test nhanh một câu đơn lẻ.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=422, detail="Văn bản không được để trống.")

    model_instance = get_embedding_model(model)
    vector = model_instance.encode(
        [cleaned_text],
        normalize_embeddings=normalize,
        show_progress_bar=False,
    )
    res_list = vector.tolist() if hasattr(vector, "tolist") else [list(v) for v in vector]

    return {
        "model": model,
        "dimension": len(res_list[0]) if res_list else 0,
        "embedding": res_list[0],
    }
