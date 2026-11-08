import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.source_merge import (
    DEFAULT_INPUT_FILE,
    merge_ranked_file,
    render_merged_documents_as_markdown,
)

DEFAULT_OUTPUT_FILE = (
    Path(__file__).resolve().parent / "output" / "scraped_data_merged.md"
)


def main() -> int:
    try:
        merged = merge_ranked_file()
        rendered = render_merged_documents_as_markdown(merged)
        DEFAULT_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT_FILE.write_text(rendered, encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        print(f"Lỗi khi gộp hoặc lưu dữ liệu: {exc}")
        return 1

    print(f"Đã gộp {len(merged)} nguồn từ '{DEFAULT_INPUT_FILE}'.")
    print(f"Đã lưu kết quả vào '{DEFAULT_OUTPUT_FILE}'.")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
