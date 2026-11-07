import argparse
import json
import math
from pathlib import Path
from typing import Any

import requests

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL = "intfloat/multilingual-e5-small"
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


def request_embeddings(
    api_url: str,
    texts: list[str],
    model: str,
) -> tuple[list[list[float]], str]:
    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/embeddings",
            json={"texts": texts, "model": model, "normalize": True},
            timeout=(10, 180),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Không thể kết nối tới API embedding: {exc}") from exc

    if not response.ok:
        try:
            payload = response.json()
        except ValueError:
            detail = response.text
        else:
            detail = payload.get("detail", response.text) if isinstance(payload, dict) else response.text
        raise RuntimeError(f"API embedding trả về HTTP {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("API embedding trả về dữ liệu JSON không hợp lệ.") from exc

    embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
    if (
        not isinstance(embeddings, list)
        or len(embeddings) != len(texts)
        or not embeddings
        or not isinstance(embeddings[0], list)
        or not embeddings[0]
    ):
        raise RuntimeError("Số lượng hoặc định dạng embedding API trả về không hợp lệ.")

    dimension = len(embeddings[0])
    checked_embeddings: list[list[float]] = []
    for index, vector in enumerate(embeddings, start=1):
        if (
            not isinstance(vector, list)
            or len(vector) != dimension
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in vector
            )
        ):
            raise RuntimeError(f"Embedding thứ {index} có định dạng hoặc số chiều không hợp lệ.")
        checked_embeddings.append([float(value) for value in vector])

    return checked_embeddings, str(payload.get("model", model))


def rank_records(
    records: list[dict[str, Any]],
    query_embedding: list[float],
    record_embeddings: list[list[float]],
) -> list[dict[str, Any]]:
    if len(records) != len(record_embeddings):
        raise RuntimeError("Số embedding không khớp với số bản ghi cần xếp hạng.")

    ranked: list[dict[str, Any]] = []
    for record, embedding in zip(records, record_embeddings):
        if len(embedding) != len(query_embedding):
            raise RuntimeError("Embedding truy vấn và nội dung không cùng số chiều.")
        score = math.fsum(query_value * value for query_value, value in zip(query_embedding, embedding))
        ranked_record = dict(record)
        ranked_record["relevance_score"] = score
        ranked.append(ranked_record)

    ranked.sort(key=lambda record: record["relevance_score"], reverse=True)
    return ranked


def prepare_embedding_texts(
    query: str,
    records: list[dict[str, Any]],
    model: str,
) -> list[str]:
    if "e5" in model.casefold():
        return [
            f"query: {query}",
            *(f"passage: {record['text']}" for record in records),
        ]
    return [query, *(record["text"] for record in records)]


def save_results(output_file: Path, results: list[dict[str, Any]]) -> None:
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Không thể lưu kết quả vào '{output_file}': {exc}") from exc


def embed_single_for_testing(api_url: str, text: str, model: str) -> int:
    try:
        response = requests.get(
            f"{api_url.rstrip('/')}/embeddings/single",
            params={"text": text, "model": model},
            timeout=(10, 180),
        )
    except requests.RequestException as exc:
        print(f"Lỗi khi gọi API embedding: {exc}")
        return 1

    if not response.ok:
        print(f"Lỗi HTTP {response.status_code}: {response.text}")
        return 1

    try:
        payload = response.json()
    except ValueError:
        print("API embedding trả về dữ liệu JSON không hợp lệ.")
        return 1

    print(f"-> Model: {payload.get('model')}")
    print(f"-> Số chiều (dimension): {payload.get('dimension')}")
    print(f"-> Vector mẫu (5 phần tử đầu): {payload.get('embedding', [])[:5]}...")
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
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Địa chỉ API FastAPI")
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
        help="Chỉ kiểm tra embedding của một câu qua GET /embeddings/single.",
    )
    args = parser.parse_args()

    if args.single:
        text = args.query or SAMPLE_TEXTS[0]
        return embed_single_for_testing(args.api_url, text, args.model)

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
        embeddings, model = request_embeddings(
            args.api_url,
            prepare_embedding_texts(query.strip(), records, args.model),
            args.model,
        )
        ranked_records = rank_records(records, embeddings[0], embeddings[1:])
        save_results(args.output, ranked_records)
    except RuntimeError as exc:
        print(f"Lỗi: {exc}")
        return 1

    print(f"Đã xếp hạng {len(ranked_records)} đoạn văn bằng model '{model}'.")
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
