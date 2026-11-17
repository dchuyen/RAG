import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb
from chromadb.errors import NotFoundError

from app.services.chroma import CHROMA_COLLECTION_NAME, CHROMA_DB_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hiển thị các bản ghi đã lưu trong ChromaDB."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Số bản ghi cần hiển thị (mặc định: 10).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Vị trí bắt đầu đọc (mặc định: 0).",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit phải lớn hơn 0.")
    if args.offset < 0:
        parser.error("--offset không được âm.")

    print(f"Database: {CHROMA_DB_PATH}")
    print(f"Collection: {CHROMA_COLLECTION_NAME}")
    if not CHROMA_DB_PATH.is_dir():
        print("Chưa tìm thấy database ChromaDB.")
        return 0

    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    try:
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
    except NotFoundError:
        print("Chưa tìm thấy collection.")
        return 0

    total = collection.count()
    print(f"Tổng số bản ghi: {total}")
    if total == 0:
        return 0

    records = collection.get(
        limit=args.limit,
        offset=args.offset,
        include=["documents", "metadatas"],
    )
    if not records["ids"]:
        print(f"Không có bản ghi tại offset {args.offset}.")
        return 0

    for index, (record_id, document, metadata) in enumerate(
        zip(records["ids"], records["documents"], records["metadatas"]),
        start=args.offset + 1,
    ):
        metadata = metadata or {}
        print(f"\n--- Bản ghi {index} ---")
        print(f"ID: {record_id}")
        print(f"Nội dung: {document or ''}")
        print(f"Metadata: {json.dumps(metadata, ensure_ascii=False, indent=2)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
