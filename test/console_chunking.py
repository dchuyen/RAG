import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_INPUT = Path(__file__).resolve().parent / "output" / "scraped_data.txt"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output" / "scraped_data_processed.json"


def load_records(path: Path) -> list[dict[str, Any]]:
    """Đọc một hoặc nhiều JSON object, kể cả các object nối tiếp nhau trong file."""
    content = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    records: list[dict[str, Any]] = []
    position = 0

    while position < len(content):
        while position < len(content) and content[position].isspace():
            position += 1
        if position == len(content):
            break

        value, position = decoder.raw_decode(content, position)
        values = value if isinstance(value, list) else [value]

        for item in values:
            if not isinstance(item, dict):
                raise ValueError("Mỗi bản ghi phải là một JSON object.")
            records.append(item)

    return records


def count_tokens(text: str, tokenizer: Any) -> int:
    return len(
        tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
            verbose=False,
        )["input_ids"]
    )


def split_oversized_text(text: str, tokenizer: Any, max_tokens: int) -> list[str]:
    special_token_count = count_tokens("", tokenizer)
    token_budget = max_tokens - special_token_count
    if token_budget < 1:
        raise ValueError("max_tokens quá nhỏ để chứa token đặc biệt của mô hình.")

    chunks: list[str] = []
    remaining = text
    while remaining:
        if count_tokens(remaining, tokenizer) <= max_tokens:
            chunks.append(remaining)
            break

        encoded = tokenizer(
            remaining,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
            verbose=False,
        )
        offsets = encoded["offset_mapping"]
        end_token = min(token_budget, len(offsets))

        while end_token > 0:
            end = offsets[end_token - 1][1]
            whitespace = remaining.rfind(" ", 0, end)
            if whitespace > 0:
                end = whitespace

            chunk = remaining[:end].strip()
            if chunk and count_tokens(chunk, tokenizer) <= max_tokens:
                break
            end_token -= 1
        else:
            raise ValueError("Không thể chia văn bản thành chunk trong giới hạn token.")

        chunks.append(chunk)
        remaining = remaining[end:].strip()

    return chunks


def split_text_by_tokens(text: str, tokenizer: Any, max_tokens: int) -> list[str]:
    normalized_text = re.sub(r"\s+", " ", text).strip()
    if not normalized_text:
        return []

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text)
        if sentence.strip()
    ]
    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        candidate = f"{current_chunk} {sentence}".strip()
        if count_tokens(candidate, tokenizer) <= max_tokens:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk)
            current_chunk = ""

        if count_tokens(sentence, tokenizer) > max_tokens:
            chunks.extend(split_oversized_text(sentence, tokenizer, max_tokens))
        else:
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def records_with_chunk_metadata(
    record: dict[str, Any],
    index: int,
    tokenizer: Any,
    max_tokens: int,
) -> list[dict[str, Any]]:
    text = record.get("text", "")
    if not isinstance(text, str):
        raise ValueError(f"Trường 'text' của bản ghi {index} phải là chuỗi.")

    metadata = {key: value for key, value in record.items() if key != "text"}
    return [
        {"text": chunk, "metadata": metadata}
        for chunk in split_text_by_tokens(text, tokenizer, max_tokens)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chia văn bản thành các chunk theo giới hạn token và xuất JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"File JSON đầu vào (mặc định: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"File JSON đầu ra (mặc định: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Mô hình Hugging Face dùng để đếm token (mặc định: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=450,
        help="Số token tối đa mỗi chunk, tính cả token đặc biệt (mặc định: 450).",
    )
    args = parser.parse_args()

    if args.max_tokens < 1:
        parser.error("--max-tokens phải lớn hơn 0.")

    records = load_records(args.input)
    if not records:
        parser.error(f"Không tìm thấy bản ghi JSON trong '{args.input}'.")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if args.max_tokens > tokenizer.model_max_length:
        parser.error(
            f"--max-tokens không được vượt quá giới hạn {tokenizer.model_max_length} "
            f"token của mô hình '{args.model}'."
        )

    processed_records = [
        chunk_record
        for index, record in enumerate(records, start=1)
        for chunk_record in records_with_chunk_metadata(
            record, index, tokenizer, args.max_tokens
        )
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(processed_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Đã xử lý {len(records)} bản ghi và lưu vào '{args.output}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
