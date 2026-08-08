from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple


IMAGE_EXTENSIONS = r"jpg|jpeg|png|gif|bmp|webp|svg"


def clean_markdown(content: str) -> Tuple[str, Dict[str, int]]:
    stats = {
        "page_idx": 0,
        "images": 0,
        "empty_headings": 0,
        "blank_lines_merged": 0,
        "original_lines": content.count("\n"),
    }

    content, count = re.subn(r"<page_idx:\d+>\s*", "", content)
    stats["page_idx"] = count

    content, count1 = re.subn(r"!\[.*?\]\([^)]+\)\s*", "", content)
    content, count2 = re.subn(rf"[a-zA-Z0-9_\-/]+\.({IMAGE_EXTENSIONS})\)?", "", content, flags=re.IGNORECASE)
    content, count3 = re.subn(rf"\([^)]*\.({IMAGE_EXTENSIONS})\)", "", content, flags=re.IGNORECASE)
    content, count4 = re.subn(r"\(\s*\)", "", content)
    stats["images"] = count1 + count2 + count3 + count4

    content, count = re.subn(r"^#+\s*$", "", content, flags=re.MULTILINE)
    stats["empty_headings"] = count

    stats["blank_lines_merged"] = len(re.findall(r"\n{3,}", content))
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = "\n".join(line.rstrip() for line in content.splitlines())
    content = content.strip()
    stats["final_lines"] = content.count("\n")
    return content, stats


def clean_markdown_file(input_path: str, output_path: str | None = None) -> Tuple[Path, Dict[str, int]]:
    source_path = Path(input_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input markdown file does not exist: {source_path}")

    destination = Path(output_path) if output_path else source_path
    cleaned, stats = clean_markdown(source_path.read_text(encoding="utf-8"))
    destination.write_text(cleaned, encoding="utf-8")
    return destination, stats
