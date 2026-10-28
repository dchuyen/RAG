from typing import Any

from fastapi import APIRouter, HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chunks", tags=["chunks"])


class ChunkRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Văn bản cần cắt thành các đoạn nhỏ.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata được gắn với từng chunk.",
    )
    chunk_size: int = Field(
        default=1000,
        gt=0,
        description="Kích thước tối đa mỗi chunk tính theo ký tự.",
    )
    chunk_overlap: int = Field(
        default=100,
        ge=0,
        description="Số ký tự chồng lấp giữa các chunk.",
    )


class ChunkItem(BaseModel):
    text: str
    metadata: dict[str, Any]


class ChunkResponse(BaseModel):
    total_chunks: int
    chunks: list[ChunkItem]


@router.post("/split", response_model=ChunkResponse)
def split_into_chunks(payload: ChunkRequest) -> ChunkResponse:
    """Cắt văn bản thành các chunk, ưu tiên giữ nguyên ranh giới đoạn văn."""
    cleaned_text = payload.text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=422,
            detail="Văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )
    if payload.chunk_overlap >= payload.chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap phải nhỏ hơn chunk_size.",
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_text(cleaned_text)
    chunk_items = [
        ChunkItem(text=chunk, metadata=payload.metadata.copy()) for chunk in chunks
    ]
    return ChunkResponse(total_chunks=len(chunk_items), chunks=chunk_items)
