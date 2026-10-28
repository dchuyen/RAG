import argparse
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any

import requests

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL = "intfloat/multilingual-e5-small"


def request_semantic_search(
    api_url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/semantic-search",
            json=payload,
            timeout=(10, 300),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Không thể kết nối tới API tại {api_url}: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        if not response.ok:
            raise RuntimeError(
                f"API trả về HTTP {response.status_code}: {response.text}"
            ) from exc
        raise RuntimeError("API trả về dữ liệu JSON không hợp lệ.") from exc

    if not response.ok:
        detail = result.get("detail", result) if isinstance(result, dict) else result
        raise RuntimeError(f"API trả về HTTP {response.status_code}: {detail}")
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise RuntimeError("Phản hồi API không đúng định dạng semantic-search.")

    timings = result.get("step_timings")
    timing_fields = (
        "search_seconds",
        "scrape_seconds",
        "chunk_seconds",
        "embedding_seconds",
        "ranking_seconds",
    )
    if not isinstance(timings, dict) or any(
        isinstance(timings.get(field), bool)
        or not isinstance(timings.get(field), (int, float))
        or not math.isfinite(timings[field])
        or timings[field] < 0
        for field in timing_fields
    ):
        raise RuntimeError("Phản hồi API thiếu thời gian hoặc có thời gian từng bước không hợp lệ.")

    for index, item in enumerate(result["results"], start=1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("text"), str)
            or not isinstance(item.get("metadata"), dict)
            or not isinstance(item.get("relevance_score"), (int, float))
        ):
            raise RuntimeError(f"Kết quả xếp hạng thứ {index} có định dạng không hợp lệ.")
    return result


def save_response(output_file: Path, result: dict[str, Any]) -> None:
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Không thể lưu phản hồi vào '{output_file}': {exc}") from exc


def print_results(result: dict[str, Any], client_wait_seconds: float) -> None:
    print(
        "Tìm thấy "
        f"{result.get('searched_url_count', 0)} URL, cào thành công "
        f"{result.get('scraped_page_count', 0)} trang, tạo "
        f"{result.get('total_chunks', 0)} đoạn."
    )
    print(f"Model: {result.get('model', '(không rõ)')}")
    print("\nThời gian xử lý:")
    print(f"- Search: {result['step_timings']['search_seconds']:.3f} giây")
    print(f"- Scrape (tổng các trang): {result['step_timings']['scrape_seconds']:.3f} giây")
    print(f"- Chunks: {result['step_timings']['chunk_seconds']:.3f} giây")
    print(f"- Embeddings: {result['step_timings']['embedding_seconds']:.3f} giây")
    print(f"- Ranking: {result['step_timings']['ranking_seconds']:.3f} giây")
    print(f"- Tổng thời gian chờ API: {client_wait_seconds:.3f} giây")

    failures = result.get("failed_pages", [])
    if isinstance(failures, list) and failures:
        print(f"\nTrang cào thất bại: {len(failures)}")
        for failure in failures:
            if isinstance(failure, dict):
                print(
                    f"- HTTP {failure.get('status_code', '?')} "
                    f"{failure.get('url', '')}: {failure.get('detail', '')}"
                )

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gửi truy vấn tới API tìm kiếm ngữ nghĩa trên web."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Nội dung tìm kiếm; nếu bỏ trống, chương trình sẽ hỏi.",
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Địa chỉ API FastAPI")
    parser.add_argument("--max-results", type=int, default=1, choices=range(1, 51))
    parser.add_argument("--region", default="wt-wt", help="Mã vùng tìm kiếm")
    parser.add_argument(
        "--safesearch",
        choices=("off", "moderate", "strict"),
        default="moderate",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model embedding")
    parser.add_argument(
        "--output",
        type=Path,
        help="File JSON tùy chọn để lưu toàn bộ phản hồi từ API.",
    )
    args = parser.parse_args()

    query = args.query
    if query is None:
        try:
            query = input("Nội dung tìm kiếm (để trống để thoát): ").strip()
        except EOFError:
            print()
            return 0
    if not query.strip():
        return 0
    if args.chunk_size <= 0:
        parser.error("--chunk-size phải lớn hơn 0.")
    if args.chunk_overlap < 0:
        parser.error("--chunk-overlap không được âm.")
    if args.chunk_overlap >= args.chunk_size:
        parser.error("--chunk-overlap phải nhỏ hơn --chunk-size.")

    payload = {
        "query": query.strip(),
        "max_results": args.max_results,
        "region": args.region,
        "safesearch": args.safesearch,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "model": args.model,
    }

    try:
        request_started = perf_counter()
        result = request_semantic_search(args.api_url, payload)
        client_wait_seconds = perf_counter() - request_started
        print_results(result, client_wait_seconds)
        if args.output:
            save_response(args.output, result)
            print(f"\nĐã lưu phản hồi JSON vào '{args.output}'.")
    except RuntimeError as exc:
        print(f"Lỗi: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
