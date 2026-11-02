from typing import Any

from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(
    text: str,
    metadata: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=422,
            detail="Văn bản không được để trống hoặc chỉ chứa khoảng trắng.",
        )
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail="chunk_overlap phải nhỏ hơn chunk_size.",
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return [
        {"text": chunk, "metadata": metadata.copy()}
        for chunk in splitter.split_text(cleaned_text)
    ]
