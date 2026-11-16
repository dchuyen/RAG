import json
from pathlib import Path
from typing import Any

OUTPUT_DIRECTORY = Path(__file__).resolve().parents[2] / "test" / "output"
DEFAULT_INPUT_FILE = OUTPUT_DIRECTORY / "scraped_data_ranked.json"


def load_ranked_documents(
    input_file: Path = DEFAULT_INPUT_FILE,
) -> list[dict[str, Any]]:
    try:
        data = json.loads(input_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Không thể đọc file '{input_file}': {exc}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"File '{input_file}' không phải JSON UTF-8 hợp lệ: {exc}") from exc

    if not isinstance(data, list):
        raise RuntimeError(f"File '{input_file}' phải chứa một JSON array.")

    documents: list[dict[str, Any]] = []
    for index, document in enumerate(data, start=1):
        if not isinstance(document, dict):
            raise RuntimeError(f"Bản ghi {index} trong '{input_file}' phải là JSON object.")
        if not isinstance(document.get("text"), str):
            raise RuntimeError(f"Trường 'text' của bản ghi {index} phải là chuỗi.")
        if not isinstance(document.get("metadata"), dict):
            raise RuntimeError(f"Trường 'metadata' của bản ghi {index} phải là JSON object.")
        score = document.get("relevance_score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise RuntimeError(
                f"Trường 'relevance_score' của bản ghi {index} phải là số."
            )
        documents.append(document)

    return documents


def sort_ranked_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ranked = [document.copy() for document in documents]
    ranked.sort(
        key=lambda document: document["relevance_score"],
        reverse=True,
    )
    return ranked


def render_documents_as_markdown(documents: list[dict[str, Any]]) -> str:
    sections = ["# Kết quả theo mức độ liên quan"]
    for index, document in enumerate(documents, start=1):
        metadata = document["metadata"]
        title = metadata.get("title")
        source = metadata.get("source")
        heading = title if isinstance(title, str) and title.strip() else (
            source if isinstance(source, str) and source.strip() else f"Nguồn {index}"
        )
        sections.extend(
            [
                f"## {index}. {heading}",
                "",
                f"- Nguồn: {source}" if isinstance(source, str) and source.strip() else "- Nguồn: không rõ",
            ]
        )

        date = metadata.get("date")
        if isinstance(date, str) and date.strip():
            sections.append(f"- Ngày: {date}")
        sections.append(f"- Điểm liên quan: {document['relevance_score']}")
        sections.extend(["", document["text"], ""])

    return "\n".join(sections).rstrip() + "\n"