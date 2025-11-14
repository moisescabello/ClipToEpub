#!/usr/bin/env python3
from __future__ import annotations

from .base import LLMRequest, LLMProvider
from ..llm_anthropic import process_text  # type: ignore[attr-defined]


class AnthropicProvider(LLMProvider):
    def process(self, request: LLMRequest) -> str:
        return process_text(
            request.text,
            api_key=request.api_key,
            model=request.model,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout_s=request.timeout_s,
            retries=request.retries,
        )


__all__ = ["AnthropicProvider"]

