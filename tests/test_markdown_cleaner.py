import unittest

from hierarchical_structure_restoration.markdown_cleaner import clean_markdown


class MarkdownCleanerTests(unittest.TestCase):
    def test_clean_markdown_removes_page_tags_images_and_extra_blank_lines(self):
        source = """<page_idx:3>\n# Heading\n\n![](figure.jpg)\n\n\nParagraph\n"""
        cleaned, stats = clean_markdown(source)
        self.assertEqual(cleaned, "# Heading\n\nParagraph")
        self.assertGreaterEqual(stats["page_idx"], 1)
        self.assertGreaterEqual(stats["images"], 1)


if __name__ == "__main__":
    unittest.main()
