from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.chunks import split_text

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
    chunks = split_text(
        payload.text,
        payload.metadata,
        payload.chunk_size,
        payload.chunk_overlap,
    )
    return ChunkResponse(total_chunks=len(chunks), chunks=chunks)
