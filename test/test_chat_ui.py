import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.chat_ui import router


class ChatUiTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_chat_page_is_served(self) -> None:
        response = self.client.get("/chat")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('fetch("/chat/groq"', response.text)
        self.assertIn('id="chat-form"', response.text)
        self.assertIn("Cuộc trò chuyện mới", response.text)


if __name__ == "__main__":
    unittest.main()
