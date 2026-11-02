from pathlib import Path


def get_chat_page_path() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "groq_chat.html"
