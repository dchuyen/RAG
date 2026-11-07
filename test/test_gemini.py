import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.gemini import _format_search_results


class FormatSearchResultsTests(unittest.TestCase):
    def test_formats_only_the_result_with_the_highest_relevance_score(self) -> None:
        results = [
            {
                "text": "Nguồn điểm thấp",
                "metadata": {"source": "https://low.example", "title": "Nguồn thấp"},
                "relevance_score": 0.4,
            },
            {
                "text": "Nguồn điểm cao",
                "metadata": {"source": "https://high.example", "title": "Nguồn cao"},
                "relevance_score": 0.95,
            },
        ]

        markdown = _format_search_results({"results": results})

        self.assertIn("Nguồn điểm cao", markdown)
        self.assertIn("https://high.example", markdown)
        self.assertNotIn("Nguồn điểm thấp", markdown)
        self.assertNotIn("https://low.example", markdown)


if __name__ == "__main__":
    unittest.main()
