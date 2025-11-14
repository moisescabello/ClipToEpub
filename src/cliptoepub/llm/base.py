#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMRequest:
    text: str
    api_key: str
    model: str
    system_prompt: str
    max_tokens: int
    temperature: float
    timeout_s: int
    retries: int


class LLMProvider(Protocol):
    def process(self, request: LLMRequest) -> str: ...


__all__ = ["LLMRequest", "LLMProvider"]

