import argparse
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.gemini import DEFAULT_MODEL

DEFAULT_API_URL = "http://127.0.0.1:8000"


def send_message(
    api_url: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int | None,
) -> str:
    payload: dict[str, Any] = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/chat/gemini",
            json=payload,
            timeout=(10, 120),
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
    if not isinstance(result, dict) or not isinstance(result.get("message"), str):
        raise RuntimeError("Phản hồi API không đúng định dạng chat Gemini.")
    return result["message"]


def run_chat(
    api_url: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
) -> int:
    messages: list[dict[str, str]] = []
    print("Bắt đầu chat với Gemini. Nhập /exit để thoát.")

    while True:
        try:
            user_message = input("Bạn: ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\nĐã kết thúc chat.")
            return 0

        if user_message.casefold() in {"/exit", "/quit"}:
            return 0
        if not user_message:
            continue

        messages.append({"role": "user", "content": user_message})
        try:
            assistant_message = send_message(
                api_url,
                messages,
                model,
                temperature,
                max_tokens,
            )
        except RuntimeError as exc:
            messages.pop()
            print(f"Lỗi: {exc}")
            continue

        messages.append({"role": "assistant", "content": assistant_message})
        print("\nToàn bộ nội dung chat:")
        for message in messages:
            speaker = "Bạn" if message["role"] == "user" else "Gemini"
            print(f"{speaker}: {message['content']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat tương tác với Gemini qua RAG API.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Địa chỉ API FastAPI")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Tên model Gemini")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, help="Giới hạn token phản hồi")
    args = parser.parse_args()

    if not 0 <= args.temperature <= 2:
        parser.error("--temperature phải nằm trong khoảng 0 đến 2.")
    if args.max_tokens is not None and args.max_tokens <= 0:
        parser.error("--max-tokens phải lớn hơn 0.")

    return run_chat(
        args.api_url,
        args.model,
        args.temperature,
        args.max_tokens,
    )


if __name__ == "__main__":
    raise SystemExit(main())
