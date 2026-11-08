import argparse
import sys
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.gemini import DEFAULT_MODEL, chat_with_gemini


def send_message(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int | None,
) -> str:
    try:
        result = chat_with_gemini(messages, model, temperature, max_tokens)
    except HTTPException as exc:
        raise RuntimeError(
            f"Gemini service trả về HTTP {exc.status_code}: {exc.detail}"
        ) from exc
    if not isinstance(result, dict) or not isinstance(result.get("message"), str):
        raise RuntimeError("Phản hồi Gemini service không đúng định dạng.")
    return result["message"]


def run_chat(
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
    parser = argparse.ArgumentParser(description="Chat tương tác trực tiếp với Gemini.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Tên model Gemini")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, help="Giới hạn token phản hồi")
    args = parser.parse_args()

    if not 0 <= args.temperature <= 2:
        parser.error("--temperature phải nằm trong khoảng 0 đến 2.")
    if args.max_tokens is not None and args.max_tokens <= 0:
        parser.error("--max-tokens phải lớn hơn 0.")

    return run_chat(
        args.model,
        args.temperature,
        args.max_tokens,
    )


if __name__ == "__main__":
    raise SystemExit(main())
