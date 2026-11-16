import unittest
from unittest.mock import Mock, patch

import requests

from test.console_embed_rerank import embed_single_for_testing, request_api


class EmbedRerankConsoleTests(unittest.TestCase):
    def test_single_embedding_calls_api(self) -> None:
        response = Mock()
        response.json.return_value = {
            "model": "model-name",
            "embedding": [0.1, 0.2],
        }

        with patch(
            "test.console_embed_rerank.requests.request",
            return_value=response,
        ) as request:
            with patch("builtins.print"):
                result = embed_single_for_testing(
                    "example",
                    "model-name",
                    "http://localhost:9000/",
                )

        self.assertEqual(result, 0)
        request.assert_called_once_with(
            "GET",
            "http://localhost:9000/embeddings/single",
            params={"text": "example", "model": "model-name"},
            json=None,
            timeout=(10, 300),
        )

    def test_api_http_error_is_reported(self) -> None:
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            response=Mock(status_code=503, text="unavailable")
        )

        with patch(
            "test.console_embed_rerank.requests.request",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                request_api("POST", "http://localhost:8000/ranking")


if __name__ == "__main__":
    unittest.main()
