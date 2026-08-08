import unittest

from emnlp_submission.toc_extractor import parse_toc_response


class TocExtractorTests(unittest.TestCase):
    def test_parse_toc_response_accepts_json_only_contract(self):
        content = '[{"title": "Overview", "subtitles": ["Mission"]}]'
        parsed = parse_toc_response(content)
        self.assertEqual(parsed[0]["title"], "Overview")
        self.assertEqual(parsed[0]["subtitles"], ["Mission"])


if __name__ == "__main__":
    unittest.main()
