import argparse
import json
from pathlib import Path
from typing import Any

import requests

DEFAULT_INPUT = Path(__file__).resolve().parent / "output" / "scraped_data_processed.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "scraped_data_ranked.json"
DEFAULT_API_URL = "http://127.0.0.1:8000"
API_TIMEOUT = (10, 300)

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


def request_api(
    method: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        detail = response.text if response is not None else str(exc)
        status = response.status_code if response is not None else "?"
        raise RuntimeError(f"Embedding API trả về HTTP {status}: {detail}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Không thể gọi Embedding API: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("Embedding API không trả về JSON hợp lệ.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Embedding API phải trả về một JSON object.")
    return result


def embed_single_for_testing(text: str, model: str | None, api_url: str) -> int:
    params = {"text": text}
    if model is not None:
        params["model"] = model
    try:
        result = request_api(
            "GET",
            f"{api_url.rstrip('/')}/embeddings/single",
            params=params,
        )
        embedding = result.get("embedding")
        if not isinstance(embedding, list) or not all(
            isinstance(value, (int, float)) for value in embedding
        ):
            raise RuntimeError("Embedding API không trả về vector hợp lệ.")
    except RuntimeError as exc:
        print(f"Lỗi embedding: {exc}")
        return 1

    print(f"-> Model: {result.get('model', '(không rõ)')}")
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
    parser.add_argument("--model", help="Model HuggingFace (mặc định theo cấu hình API)")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"URL gốc của API (mặc định: {DEFAULT_API_URL})",
    )
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
        return embed_single_for_testing(text, args.model, args.api_url)

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
        payload: dict[str, Any] = {
            "query": query.strip(),
            "documents": records,
        }
        if args.model is not None:
            payload["model"] = args.model
        ranking = request_api(
            "POST",
            f"{args.api_url.rstrip('/')}/ranking",
            payload=payload,
        )
        ranked_results = ranking.get("results")
        if not isinstance(ranked_results, list) or not all(
            isinstance(record, dict) for record in ranked_results
        ):
            raise RuntimeError("Ranking API không trả về danh sách kết quả hợp lệ.")
        ranked_records = ranked_results
        save_results(args.output, ranked_records)
    except RuntimeError as exc:
        print(f"Lỗi: {exc}")
        return 1

    print(
        f"Đã xếp hạng {len(ranked_records)} đoạn văn bằng model "
        f"'{ranking.get('model', '(không rõ)')}'."
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
