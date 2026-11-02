from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.embeddings import DEFAULT_MODEL, encode_single_text, encode_texts

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


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


@router.post("", response_model=EmbedResponse)
def create_embeddings(payload: EmbedRequest) -> EmbedResponse:
    """
    Tạo embedding vector cho danh sách văn bản.
    """
    embeddings_list = encode_texts(payload.texts, payload.model, payload.normalize)
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
    embedding = encode_single_text(text, model, normalize)

    return {
        "model": model,
        "dimension": len(embedding),
        "embedding": embedding,
    }
