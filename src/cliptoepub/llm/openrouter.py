#!/usr/bin/env python3
from __future__ import annotations

from typing import Optional

from .base import LLMRequest, LLMProvider
from ..llm_anthropic import _process_via_openrouter, AnthropicAuthOrConfigError, AnthropicRecoverableError  # type: ignore[attr-defined]


class OpenRouterProvider(LLMProvider):
    def process(self, request: LLMRequest) -> str:
        return _process_via_openrouter(
            request.text,
            api_key=request.api_key or None,
            model=request.model,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_s=request.timeout_s,
            retries=request.retries,
        )


__all__ = ["OpenRouterProvider"]

