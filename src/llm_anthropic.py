#!/usr/bin/env python3
"""
Anthropic LLM integration with retries and simple backoff.

Provides a minimal API to process clipboard text through Anthropic and
return Markdown suitable for the converter.
"""

from __future__ import annotations

import os
import time
import random
from typing import Optional

import os
import time
import random
from typing import Optional


class AnthropicRecoverableError(Exception):
    pass


class AnthropicAuthOrConfigError(Exception):
    pass


def _sleep_backoff(attempt: int) -> None:
    # Exponential backoff with jitter: base 0.5s doubling, capped ~10s
    base = min(0.5 * (2 ** attempt), 10.0)
    time.sleep(base + random.uniform(0, 0.25))


def _extract_text_from_sdk_message(message) -> str:
    try:
        parts = []
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts).strip()
    except Exception:
        # Conservative fallback
        try:
            return str(getattr(message, "content", "")).strip()
        except Exception:
            return ""


def _extract_text_from_rest_response(data: dict) -> str:
    try:
        items = data.get("content") or []
        parts = []
        for block in items:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    except Exception:
        return ""


def _is_recoverable(exc: Exception, status_code: Optional[int] = None) -> bool:
    if status_code is not None:
        if status_code in (429, 408, 409, 425, 500, 502, 503, 504):
            return True
        if 500 <= status_code <= 599:
            return True
        return False
    # Heuristic if SDK exceptions don't expose status
    text = str(exc).lower()
    recoverable_tokens = [
        "rate limit", "overloaded", "timeout", "temporarily", "try again", "retry",
    ]
    return any(tok in text for tok in recoverable_tokens)


def _process_via_openrouter(
    text: str,
    *,
    api_key: Optional[str],
    model: str,
    system_prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout_s: int = 60,
    retries: int = 10,
) -> str:
    """Send text via OpenRouter Chat Completions API.

    Notes:
    - Supports Anthropic models available through OpenRouter such as
      'anthropic/claude-sonnet-4.5' (1M context window, provider-dependent access).
    - Uses OPENROUTER_API_KEY from environment if api_key is None/empty.
    - Expects OpenAI-compatible response with choices[0].message.content.
    """
    key = (api_key or "").strip() or os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise AnthropicAuthOrConfigError("Missing OPENROUTER_API_KEY for OpenRouter request")

    import httpx

    # Build OpenAI-compatible chat request
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Optional but recommended for some providers
        "HTTP-Referer": os.environ.get("OPENROUTER_REFERRER", "https://github.com/"),
        "X-Title": os.environ.get("OPENROUTER_TITLE", "Clipboard to ePub"),
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code in (401, 403):
                raise AnthropicAuthOrConfigError("OpenRouter authentication failed or access denied")
            if resp.status_code >= 400:
                detail = None
                try:
                    err = resp.json()
                    if isinstance(err, dict):
                        detail = err.get("error") or err.get("message") or None
                except Exception:
                    if resp.text:
                        detail = resp.text.strip()
                # Surface model not found / access issues clearly
                if detail and ("model" in str(detail).lower()) and ("not" in str(detail).lower() and "found" in str(detail).lower()):
                    raise RuntimeError(
                        f"OpenRouter model not found: '{model}'. Example: 'anthropic/claude-sonnet-4.5'"
                    )
                # Retry transient HTTP errors
                if _is_recoverable(Exception(detail or resp.text), status_code=resp.status_code):
                    raise AnthropicRecoverableError(f"HTTP {resp.status_code}")
                raise RuntimeError(f"OpenRouter error: HTTP {resp.status_code}{(' – ' + str(detail)) if detail else ''}")
            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:  # noqa: BLE001
                content = ""
            return (content or "").strip()
        except AnthropicAuthOrConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if isinstance(e, AnthropicRecoverableError) or _is_recoverable(e):
                if attempt < retries:
                    _sleep_backoff(attempt)
                    continue
                raise AnthropicRecoverableError("Exhausted retries for OpenRouter request")
            raise

    if last_exc:
        raise last_exc
    return ""


def process_text(
    text: str,
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout_s: int = 60,
    retries: int = 10,
) -> str:
    """
    Send text to Anthropic Messages API and return Markdown.

    Raises AnthropicAuthOrConfigError on 401/403 and AnthropicRecoverableError
    after all retries are exhausted for transient errors.
    """
    if not model or not system_prompt:
        raise AnthropicAuthOrConfigError("Missing model or system prompt")

    # Route to OpenRouter if model looks like an OpenRouter id or if the requested
    # Anthropic-id is known to be provided via OpenRouter (e.g., Sonnet 4.5, 1M context)
    model_lc = (model or "").strip().lower()
    if "/" in model_lc or model_lc in {"claude-4.5-sonnet", "sonnet-4.5", "claude-sonnet-4.5"}:
        # Normalize popular alias to OpenRouter's canonical id when needed
        if model_lc in {"claude-4.5-sonnet", "sonnet-4.5", "claude-sonnet-4.5"}:
            model = "anthropic/claude-sonnet-4.5"
        return _process_via_openrouter(
            text,
            api_key=api_key,  # May be empty; OPENROUTER_API_KEY is read inside
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
            retries=retries,
        )

    if not api_key:
        raise AnthropicAuthOrConfigError("Missing Anthropic API key")

    # Try SDK first; fallback to REST if SDK not installed
    try:
        from anthropic import Anthropic
        from anthropic._exceptions import APIStatusError  # type: ignore
        have_sdk = True
    except Exception:
        Anthropic = None  # type: ignore
        APIStatusError = Exception  # type: ignore
        have_sdk = False

    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            if have_sdk:
                client = Anthropic(api_key=api_key)
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": text}],
                    timeout=timeout_s,
                )
                md = _extract_text_from_sdk_message(message)
                if not md.strip():
                    md = ""
                return md
            else:
                import httpx

                headers = {
                    "content-type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": os.environ.get("ANTHROPIC_API_VERSION", "2023-06-01"),
                }
                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": float(temperature),
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": text}],
                }
                with httpx.Client(timeout=timeout_s) as client:
                    resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                if resp.status_code in (401, 403):
                    raise AnthropicAuthOrConfigError("Authentication failed or access denied")
                if resp.status_code >= 400:
                    # Try to surface Anthropic error details (e.g., model not found)
                    detail = None
                    try:
                        err = resp.json()
                        if isinstance(err, dict):
                            if "error" in err and isinstance(err["error"], dict):
                                et = err["error"].get("type")
                                em = err["error"].get("message")
                                if et and em:
                                    detail = f"{et}: {em}"
                    except Exception:
                        # Fallback to text body
                        if resp.text:
                            detail = resp.text.strip()

                    # Special-case model not found to provide a helpful hint
                    if detail and "not_found_error" in detail and "model" in detail.lower():
                        raise RuntimeError(
                            f"Model not found: '{model}'. If using Anthropic, try 'claude-4.5-sonnet'. For 1M context via OpenRouter, use 'anthropic/claude-sonnet-4.5'."
                        )

                    # Treat as recoverable depending on status
                    if _is_recoverable(Exception(detail or resp.text), status_code=resp.status_code):
                        raise AnthropicRecoverableError(f"HTTP {resp.status_code}")
                    raise RuntimeError(f"Anthropic error: HTTP {resp.status_code}{(' – ' + detail) if detail else ''}")
                data = resp.json()
                md = _extract_text_from_rest_response(data)
                return md
        except AnthropicAuthOrConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            # Try to map SDK status codes if available
            status_code: Optional[int] = None
            try:
                if have_sdk and isinstance(e, APIStatusError):  # type: ignore
                    status_code = getattr(e, "status_code", None)
            except Exception:
                status_code = None

            if isinstance(e, AnthropicRecoverableError) or _is_recoverable(e, status_code=status_code):
                if attempt < retries:
                    _sleep_backoff(attempt)
                    continue
                raise AnthropicRecoverableError("Exhausted retries for Anthropic request")
            if status_code in (401, 403):
                raise AnthropicAuthOrConfigError("Authentication failed or access denied")
            # Non-recoverable
            raise

    if last_exc:
        raise last_exc
    return ""


def sanitize_first_line(text: str) -> str:
    s = (text or "").strip().splitlines()[0] if text and text.strip() else ""
    if s.startswith("# "):
        s = s[2:]
    # Replace path-unfriendly chars
    safe = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in s).strip()
    return safe[:80] or "LLM Result"
