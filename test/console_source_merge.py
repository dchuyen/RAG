import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.source_merge import (
    DEFAULT_INPUT_FILE,
    merge_ranked_file,
    render_merged_documents_as_markdown,
)


def main() -> int:
    try:
        merged = merge_ranked_file()
    except (OSError, RuntimeError) as exc:
        print(f"Lỗi: {exc}")
        return 1

    print(f"Đã gộp {len(merged)} nguồn từ '{DEFAULT_INPUT_FILE}'.")
    print(render_merged_documents_as_markdown(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
