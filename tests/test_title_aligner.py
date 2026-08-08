import json
import tempfile
import unittest
from pathlib import Path

from emnlp_submission.title_aligner import align_document


class TitleAlignerTests(unittest.TestCase):
    def test_alignment_performs_exact_then_bm25_before_agentic(self):
        markdown = """# Corporate Governance\nIntro\n# Environmental Targets and Progress\nDetails\n"""
        toc = [
            {"title": "Corporate Governance"},
            {"title": "Environmental Targets"},
            {"title": "Social Impact"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            toc_path = Path(tmpdir) / "titles.json"
            toc_path.write_text(json.dumps(toc), encoding="utf-8")

            result = align_document(
                markdown_content=markdown,
                titles_json_path=str(toc_path),
                llm_client=None,
            )

        self.assertIn("# Corporate Governance", result.aligned_markdown)
        self.assertIn("# Environmental Targets and Progress", result.aligned_markdown)
        self.assertIn("# Social Impact", result.aligned_markdown)
        self.assertGreaterEqual(result.stats["exact_match"], 1)
        self.assertGreaterEqual(result.stats["bm25_match"], 1)
        self.assertEqual(result.stats["agentic_insert"], 1)


if __name__ == "__main__":
    unittest.main()
