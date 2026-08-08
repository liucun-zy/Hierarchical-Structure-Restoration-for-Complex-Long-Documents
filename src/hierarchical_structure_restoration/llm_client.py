from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, Optional

import requests

from .config import ModelConfig

LOGGER = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: ModelConfig):
        self.config = config

    def chat_completion(
        self,
        messages: Iterable[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> Dict[str, Any]:
        self.config.require_network_credentials()
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.config.model_name,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "n": 1,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout)
        response.raise_for_status()
        return response.json()

    def chat_text(self, messages: Iterable[Dict[str, Any]], **kwargs: Any) -> str:
        response = self.chat_completion(messages, **kwargs)
        return response["choices"][0]["message"]["content"].strip()


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> Any:
    text = text.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    for candidate in _candidate_json_strings(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("Could not parse JSON payload from model response.")


def _candidate_json_strings(text: str) -> Iterable[str]:
    stripped = text.strip()
    if stripped:
        yield stripped

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        yield stripped[array_start:array_end + 1]

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        yield stripped[object_start:object_end + 1]
