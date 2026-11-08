https://github.com/dchuyen/RAG.gitimport argparse
import sys
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.search import search_web


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "search_results.txt"


def search(
    query: str,
    max_results: int,
    region: str,
    safesearch: str,
) -> list[str]:
    try:
        return search_web(query, max_results, region, safesearch)
    except HTTPException as exc:
        raise RuntimeError(f"Search service trả về HTTP {exc.status_code}: {exc.detail}") from exc


def save_results(output_file: Path, results: list[str]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("a", encoding="utf-8") as file:
        file.write("\n".join(results) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Console để kiểm tra service tìm kiếm web."
    )
    parser.add_argument(
        "--max-results",
        type=int,
        choices=range(1, 51),
        default=5,
        metavar="1-50",
        help="Số kết quả muốn lấy (mặc định: 5)",
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
            results = search(
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
