from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image
import requests

from .llm_client import LLMClient, extract_json_payload

LOGGER = logging.getLogger(__name__)


def compress_image(image_path: str, max_size_mb: float = 1.0, quality_reduction: int = 5) -> bytes:
    max_size_bytes = max_size_mb * 1024 * 1024
    with Image.open(image_path) as image:
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        quality = 95
        buffer = io.BytesIO()
        while True:
            buffer.seek(0)
            buffer.truncate()
            image.save(buffer, format="JPEG", quality=quality)
            if buffer.tell() <= max_size_bytes or quality <= 5:
                return buffer.getvalue()
            quality -= quality_reduction


TOC_EXTRACTION_PROMPT = """
You are extracting a table of contents from the final image in the request.
Return JSON only. Do not return markdown, prose, chain-of-thought, or explanations.

Output schema:
[
  {
    "title": "Top-level heading",
    "subtitles": [
      "Second-level heading",
      {
        "title": "Second-level heading with children",
        "subtitles": ["Third-level heading"]
      }
    ]
  }
]

Rules:
1. Ignore page numbers, line numbers, leader dots, and standalone labels such as "Contents".
2. Recover wrapped headings by merging consecutive lines that belong to the same title.
3. If a short section label such as "Environment Part" appears next to or directly above a longer dominant heading, use the longer dominant heading as the primary title, or merge them when both are needed for a complete heading.
4. Infer hierarchy from font size, weight, color, indentation, spacing, and local layout.
5. When a visual block contains a dominant heading followed by smaller aligned lines, treat the dominant heading as the parent and the smaller lines as children.
6. Remove duplicates.
7. Each returned node must contain a non-empty `title` string.
""".strip()


def _retry_with_compression(client: LLMClient, messages: List[Dict[str, Any]], max_retries: int) -> Dict[str, Any]:
    retry_count = 0
    last_error: Optional[Exception] = None

    while retry_count < max_retries:
        try:
            return client.chat_completion(messages)
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            response = exc.response
            if response is None or response.status_code != 413:
                raise
            retry_count += 1
            LOGGER.warning("Image payload exceeded the request size limit. Retrying with stronger compression.")
            for message in messages:
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "image_url":
                        continue
                    image_url = item.get("image_url", {}).get("url", "")
                    if not image_url.startswith("data:image/jpeg;base64,"):
                        continue
                    raw_bytes = base64.b64decode(image_url.split(",", 1)[1])
                    temp_path = Path("_compressed_retry_image.jpg")
                    temp_path.write_bytes(raw_bytes)
                    try:
                        compressed = compress_image(str(temp_path), quality_reduction=5)
                    finally:
                        temp_path.unlink(missing_ok=True)
                    item["image_url"]["url"] = "data:image/jpeg;base64," + base64.b64encode(compressed).decode("utf-8")
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unexpected extraction failure without an HTTP error.")


def build_toc_messages(image_base64: str) -> List[Dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": TOC_EXTRACTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high",
                    },
                },
            ],
        }
    ]


def parse_toc_response(content: str) -> List[Dict[str, Any]]:
    parsed = extract_json_payload(content)
    if not isinstance(parsed, list):
        raise ValueError("The ToC response must be a JSON array.")
    _validate_toc_list(parsed)
    return parsed


def _validate_toc_list(items: Sequence[Any]) -> None:
    for item in items:
        if isinstance(item, str):
            if not item.strip():
                raise ValueError("Heading strings must be non-empty.")
            continue
        if not isinstance(item, dict):
            raise ValueError("Each ToC item must be either a string or an object.")
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Each ToC object must include a non-empty title string.")
        subtitles = item.get("subtitles", [])
        if subtitles is not None:
            if not isinstance(subtitles, list):
                raise ValueError("The subtitles field must be a list when present.")
            _validate_toc_list(subtitles)


def extract_toc_from_image(
    image_path: str,
    client: LLMClient,
    *,
    output_path: str | None = None,
) -> List[Dict[str, Any]]:
    image_file = Path(image_path).resolve()
    if not image_file.exists():
        raise FileNotFoundError(f"Input image file does not exist: {image_file}")

    image_base64 = base64.b64encode(image_file.read_bytes()).decode("utf-8")
    messages = build_toc_messages(image_base64)
    response = _retry_with_compression(client, messages, client.config.max_retries)
    content = response["choices"][0]["message"]["content"]
    parsed = parse_toc_response(content)

    if output_path:
        destination = Path(output_path)
        destination.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return parsed
