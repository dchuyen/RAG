import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.markdown_export import (
    DEFAULT_INPUT_FILE,
    load_ranked_documents,
    render_documents_as_markdown,
    sort_ranked_documents,
)

DEFAULT_OUTPUT_FILE = (
    Path(__file__).resolve().parent / "output" / "scraped_data_markdown.md"
)


def main() -> int:
    try:
        documents = sort_ranked_documents(load_ranked_documents())
        rendered = render_documents_as_markdown(documents)
        DEFAULT_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT_FILE.write_text(rendered, encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        print(f"Lỗi khi chuyển đổi hoặc lưu dữ liệu: {exc}")
        return 1

    print(f"Đã chuyển {len(documents)} bản ghi từ '{DEFAULT_INPUT_FILE}'.")
    print(f"Đã lưu kết quả vào '{DEFAULT_OUTPUT_FILE}'.")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())