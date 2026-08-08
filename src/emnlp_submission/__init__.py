"""Table-of-contents extraction and Markdown heading-alignment utilities."""

__version__ = "0.1.0"

from .config import ModelConfig
from .markdown_cleaner import clean_markdown, clean_markdown_file
from .toc_extractor import extract_toc_from_image, parse_toc_response
from .title_aligner import AlignmentResult, align_document

__all__ = [
    "AlignmentResult",
    "ModelConfig",
    "align_document",
    "clean_markdown",
    "clean_markdown_file",
    "extract_toc_from_image",
    "parse_toc_response",
]
