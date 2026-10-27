import argparse
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def scrape_api(api_url: str, webpage_url: str) -> dict[str, Any]:
    params = urlencode({"url": webpage_url})
    endpoint = f"{api_url.rstrip('/')}/scrape?{params}"

    try:
        with urlopen(endpoint, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(error_body)
        except json.JSONDecodeError:
            detail = error_body
        else:
            detail = error_payload.get("detail", error_body) if isinstance(error_payload, dict) else error_body
        raise RuntimeError(f"API trả về HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Không thể kết nối tới API tại {api_url}: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("API trả về dữ liệu JSON không hợp lệ.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Phản hồi API không có định dạng JSON object.")
    return payload


def save_result(output_file: Path, result: dict[str, Any]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("a", encoding="utf-8") as file:
        if file.tell() > 0:
            file.write("\n")
        file.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


def scrape_and_print(
    api_url: str,
    webpage_url: str,
    output_file: Path,
) -> bool:
    try:
        result = scrape_api(api_url, webpage_url)
    except RuntimeError as exc:
        print(f"Lỗi: {exc}")
        return False

    try:
        save_result(output_file, result)
    except OSError as exc:
        print(f"Lỗi khi lưu dữ liệu vào '{output_file}': {exc}")
        return False

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Console client để kiểm tra API cào dữ liệu web."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL cần cào; nếu bỏ trống, chương trình sẽ hỏi URL tương tác.",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Địa chỉ gốc của FastAPI (mặc định: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_data.txt"),
        help="File văn bản để lưu kết quả (mặc định: scraped_data.txt)",
    )
    args = parser.parse_args()

    if args.url:
        return 0 if scrape_and_print(args.api_url, args.url, args.output) else 1

    print("Console cào dữ liệu web. Nhập URL trống để thoát.")
    while True:
        try:
            webpage_url = input("\nURL cần cào: ").strip()
        except EOFError:
            print()
            break
        if not webpage_url:
            break
        scrape_and_print(args.api_url, webpage_url, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
