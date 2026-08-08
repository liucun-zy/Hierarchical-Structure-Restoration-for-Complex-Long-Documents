from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelConfig:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "Qwen3.5-27B"
    timeout: int = 120
    max_retries: int = 3

    @classmethod
    def from_env(
        cls,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> "ModelConfig":
        return cls(
            api_key=api_key if api_key is not None else os.getenv("LLM_API_KEY"),
            base_url=base_url if base_url is not None else os.getenv("LLM_BASE_URL"),
            model_name=model_name if model_name is not None else os.getenv("LLM_MODEL", "Qwen3.5-27B"),
            timeout=timeout if timeout is not None else int(os.getenv("LLM_TIMEOUT", "120")),
            max_retries=max_retries if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "3")),
        )

    def require_network_credentials(self) -> None:
        if not self.api_key:
            raise ValueError("Missing API key. Set LLM_API_KEY or pass --api-key.")
        if not self.base_url:
            raise ValueError("Missing base URL. Set LLM_BASE_URL or pass --base-url.")
