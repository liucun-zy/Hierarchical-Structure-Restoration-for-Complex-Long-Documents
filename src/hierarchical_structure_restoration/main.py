from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .config import ModelConfig
from .llm_client import LLMClient
from .markdown_cleaner import clean_markdown_file
from .toc_extractor import extract_toc_from_image
from .title_aligner import align_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore Markdown heading hierarchy from table-of-contents data.")
    parser.add_argument("--markdown-input", help="Path to the input markdown file.")
    parser.add_argument("--toc-json", help="Path to an existing titles.json file.")
    parser.add_argument("--toc-image", help="Path to a ToC image used for visual extraction.")
    parser.add_argument("--cleaned-output", required=True, help="Path to write the cleaned markdown file.")
    parser.add_argument("--aligned-output", required=True, help="Path to write the aligned markdown file.")
    parser.add_argument("--extracted-toc-output", help="Optional path to save extracted ToC JSON.")
    parser.add_argument("--api-key", help="Override LLM_API_KEY.")
    parser.add_argument("--base-url", help="Override LLM_BASE_URL.")
    parser.add_argument("--model", default="Qwen3.5-27B", help="Override the default model name.")
    parser.add_argument("--timeout", type=int, default=120, help="LLM request timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=3, help="LLM request retry count.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.markdown_input:
        parser.error("--markdown-input is required.")
    if not args.toc_json and not args.toc_image:
        parser.error("Provide either --toc-json or --toc-image.")

    cleaned_output, _ = clean_markdown_file(args.markdown_input, args.cleaned_output)

    config = ModelConfig.from_env(
        api_key=args.api_key,
        base_url=args.base_url,
        model_name=args.model,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )
    llm_client = None

    toc_json_path = args.toc_json
    if args.toc_image:
        llm_client = LLMClient(config)
        extracted_output = args.extracted_toc_output or str(Path(args.aligned_output).with_suffix(".titles.json"))
        extracted_toc = extract_toc_from_image(args.toc_image, llm_client, output_path=extracted_output)
        toc_json_path = extracted_output
        Path(extracted_output).write_text(json.dumps(extracted_toc, ensure_ascii=False, indent=2), encoding="utf-8")

    if llm_client is None and config.api_key and config.base_url:
        llm_client = LLMClient(config)

    result = align_document(
        markdown_content=Path(cleaned_output).read_text(encoding="utf-8"),
        titles_json_path=toc_json_path,
        llm_client=llm_client,
    )
    Path(args.aligned_output).write_text(result.aligned_markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
