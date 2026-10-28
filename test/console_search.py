import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "search_results.txt"


def search_api(
    api_url: str,
    query: str,
    max_results: int,
    region: str,
    safesearch: str,
) -> list[str]:
    params = urlencode(
        {
            "q": query,
            "max_results": max_results,
            "region": region,
            "safesearch": safesearch,
        }
    )
    url = f"{api_url.rstrip('/')}/search?{params}"

    try:
        with urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(error_body).get("detail", error_body)
        except json.JSONDecodeError:
            detail = error_body
        raise RuntimeError(f"API trả về HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Không thể kết nối tới API tại {api_url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("API trả về dữ liệu JSON không hợp lệ.") from exc

    if not isinstance(payload, list) or not all(
        isinstance(link, str) for link in payload
    ):
        raise RuntimeError("Danh sách kết quả API có định dạng không hợp lệ.")
    return payload


def save_results(output_file: Path, results: list[str]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("a", encoding="utf-8") as file:
        file.write("\n".join(results) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Console client để kiểm tra API tìm kiếm web."
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Địa chỉ gốc của FastAPI (mặc định: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        choices=range(1, 51),
        default=1,
        metavar="1-50",
        help="Số kết quả muốn lấy (mặc định: 1)",
    )
    parser.add_argument("--region", default="wt-wt", help="Mã vùng tìm kiếm")
    parser.add_argument(
        "--safesearch",
        choices=("off", "moderate", "strict"),
        default="moderate",
        help="Chế độ SafeSearch",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"File văn bản để lưu các URL tìm được (mặc định: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print("Console tìm kiếm web. Nhập truy vấn trống để thoát.")
    while True:
        try:
            query = input("\nTừ khóa tìm kiếm: ").strip()
        except EOFError:
            print()
            break
        if not query:
            break

        try:
            results = search_api(
                args.api_url,
                query,
                args.max_results,
                args.region,
                args.safesearch,
            )
        except RuntimeError as exc:
            print(f"Lỗi: {exc}")
            continue

        if not results:
            print("Không tìm thấy kết quả.")
            continue

        try:
            save_results(args.output, results)
        except OSError as exc:
            print(f"Lỗi khi lưu liên kết vào '{args.output}': {exc}")

        for index, link in enumerate(results, start=1):
            print(f"{index}. {link}")


if __name__ == "__main__":
    main()
