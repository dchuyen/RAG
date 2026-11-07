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


def merge_ranked_documents_by_source(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    document_by_source: dict[str, dict[str, Any]] = {}

    for document in documents:
        metadata = document["metadata"]
        source = metadata.get("source")
        if not isinstance(source, str) or not source.strip():
            merged.append(document.copy())
            continue

        existing = document_by_source.get(source)
        if existing is None:
            existing = {
                **document,
                "metadata": metadata.copy(),
            }
            document_by_source[source] = existing
            merged.append(existing)
            continue

        existing["text"] = f"{existing['text']}\n\n{document['text']}"
        existing["relevance_score"] = max(
            existing["relevance_score"],
            document["relevance_score"],
        )

    merged.sort(
        key=lambda document: document["relevance_score"],
        reverse=True,
    )
    return merged


def render_merged_documents_as_markdown(documents: list[dict[str, Any]]) -> str:
    sections = ["# Kết quả gộp theo nguồn"]
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


def merge_ranked_file(
    input_file: Path = DEFAULT_INPUT_FILE,
) -> list[dict[str, Any]]:
    return merge_ranked_documents_by_source(load_ranked_documents(input_file))
