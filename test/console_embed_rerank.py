import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.embeddings import DEFAULT_MODEL, encode_single_text
from app.services.ranking import rank_documents

DEFAULT_INPUT = Path(__file__).resolve().parent / "output" / "scraped_data_processed.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "scraped_data_ranked.json"

SAMPLE_TEXTS = [
    "Hà Nội là thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.",
    "Trí tuệ nhân tạo đang làm thay đổi toàn diện ngành công nghệ thông tin.",
    "Mô hình ngôn ngữ lớn và kỹ thuật RAG giúp tìm kiếm thông tin chính xác hơn.",
]


def load_records(input_file: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(input_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Không thể đọc file '{input_file}': {exc}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"File '{input_file}' không phải JSON UTF-8 hợp lệ: {exc}") from exc

    if not isinstance(data, list):
        raise RuntimeError(f"File '{input_file}' phải chứa một JSON array.")

    records: list[dict[str, Any]] = []
    for index, record in enumerate(data, start=1):
        if not isinstance(record, dict):
            raise RuntimeError(f"Bản ghi {index} trong '{input_file}' phải là JSON object.")
        text = record.get("text")
        if not isinstance(text, str):
            raise RuntimeError(f"Trường 'text' của bản ghi {index} phải là chuỗi.")
        if text.strip():
            records.append(record)

    if not records:
        raise RuntimeError(f"Không tìm thấy nội dung 'text' trong '{input_file}'.")
    return records


def save_results(output_file: Path, results: list[dict[str, Any]]) -> None:
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Không thể lưu kết quả vào '{output_file}': {exc}") from exc


def embed_single_for_testing(text: str, model: str) -> int:
    try:
        embedding = encode_single_text(text, model)
    except HTTPException as exc:
        print(f"Lỗi embedding (HTTP {exc.status_code}): {exc.detail}")
        return 1

    print(f"-> Model: {model}")
    print(f"-> Số chiều (dimension): {len(embedding)}")
    print(f"-> Vector mẫu (5 phần tử đầu): {embedding[:5]}...")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tìm kiếm nội dung bằng embedding và xếp hạng theo độ liên quan."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Nội dung tìm kiếm; nếu bỏ trống, chương trình sẽ hỏi.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model HuggingFace")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"File JSON chứa các trường text (mặc định: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"File JSON lưu kết quả đã xếp hạng (mặc định: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Chỉ kiểm tra embedding của một câu.",
    )
    args = parser.parse_args()

    if args.single:
        text = args.query or SAMPLE_TEXTS[0]
        return embed_single_for_testing(text, args.model)

    query = args.query
    if query is None:
        try:
            query = input("Nội dung tìm kiếm (để trống để thoát): ").strip()
        except EOFError:
            print()
            return 0
    if not query.strip():
        return 0

    try:
        records = load_records(args.input)
        for index, record in enumerate(records, start=1):
            metadata = record.get("metadata", {})
            if not isinstance(metadata, dict):
                raise RuntimeError(
                    f"Trường 'metadata' của bản ghi {index} phải là JSON object."
                )
            record["metadata"] = metadata
        ranking = rank_documents(query.strip(), records, args.model)
        ranked_records = ranking["results"]
        save_results(args.output, ranked_records)
    except HTTPException as exc:
        print(f"Lỗi xếp hạng (HTTP {exc.status_code}): {exc.detail}")
        return 1
    except RuntimeError as exc:
        print(f"Lỗi: {exc}")
        return 1

    print(
        f"Đã xếp hạng {len(ranked_records)} đoạn văn bằng model "
        f"'{ranking['model']}'."
    )
    print(f"Đã lưu kết quả vào '{args.output}'.")
    for index, record in enumerate(ranked_records[:5], start=1):
        metadata = record.get("metadata")
        title = (
            metadata.get("title", "(không có tiêu đề)")
            if isinstance(metadata, dict)
            else "(không có tiêu đề)"
        )
        print(f"{index}. {title} — {record['relevance_score']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
