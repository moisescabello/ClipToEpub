#!/usr/bin/env python3
"""
LLM configuration utilities

Centralizes prompt schema normalization and parameter resolution for
providers and per-prompt overrides. Used by menubar/tray apps and settings UIs.

Responsibilities:
- Normalize llm_prompts (5 items), active index, and toggle flags.
- Migrate legacy anthropic_prompt into first prompt if empty.
- Resolve provider/api_key/model and numeric params, applying per-prompt
  overrides when enabled.
- Provide menu label helpers for LLM prompts.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import os


PROMPT_SLOTS = 5


def ensure_llm_config(cfg: Dict) -> Dict:
    """Ensure llm-related keys exist and are normalized in-place.

    - Guarantees exactly 5 prompts objects with keys: name, text, overrides.
    - Migrates legacy anthropic_prompt to slot 0 if all prompts are empty.
    - Clamps llm_prompt_active to [0..4].
    - Coerces llm_per_prompt_overrides to bool.

    Returns the same dict for convenience.
    """
    try:
        prompts = cfg.get("llm_prompts")
        if not isinstance(prompts, list):
            prompts = []
        norm: List[Dict] = []
        for i in range(PROMPT_SLOTS):
            item = prompts[i] if i < len(prompts) else {}
            name = str(item.get("name", "")) if isinstance(item, dict) else ""
            text = str(item.get("text", "")) if isinstance(item, dict) else ""
            overrides = item.get("overrides", {}) if isinstance(item, dict) else {}
            if not isinstance(overrides, dict):
                overrides = {}
            norm.append({"name": name, "text": text, "overrides": overrides})
        cfg["llm_prompts"] = norm

        # Migrate from legacy single prompt if no multi-prompts have text
        if not any(p.get("text") for p in norm) and cfg.get("anthropic_prompt"):
            cfg["llm_prompts"][0]["text"] = str(cfg.get("anthropic_prompt", ""))
            cfg.setdefault("llm_prompt_active", 0)

        try:
            idx = int(cfg.get("llm_prompt_active", 0))
        except Exception:
            idx = 0
        if idx < 0 or idx >= PROMPT_SLOTS:
            cfg["llm_prompt_active"] = 0
        else:
            cfg["llm_prompt_active"] = idx

        cfg["llm_per_prompt_overrides"] = bool(cfg.get("llm_per_prompt_overrides", False))
    except Exception:
        cfg["llm_prompts"] = [
            {"name": "", "text": "", "overrides": {}},
            {"name": "", "text": "", "overrides": {}},
            {"name": "", "text": "", "overrides": {}},
            {"name": "", "text": "", "overrides": {}},
            {"name": "", "text": "", "overrides": {}},
        ]
        cfg["llm_prompt_active"] = 0
        cfg["llm_per_prompt_overrides"] = False
    return cfg


def _clamp_index(idx: int) -> int:
    return 0 if idx < 0 else (PROMPT_SLOTS - 1 if idx >= PROMPT_SLOTS else idx)


def get_prompt_menu_items(cfg: Dict) -> List[Tuple[int, str]]:
    """Return (index, label) for prompts that have non-empty text.

    Label fallback: 'Prompt X' when no name is set.
    """
    ensure_llm_config(cfg)
    items: List[Tuple[int, str]] = []
    for i, p in enumerate(cfg.get("llm_prompts", [])[:PROMPT_SLOTS]):
        try:
            txt = (p or {}).get("text", "") if isinstance(p, dict) else ""
            if not str(txt).strip():
                continue
            name = (p or {}).get("name", "") if isinstance(p, dict) else ""
            label = (name or "").strip() or f"Prompt {i+1}"
            items.append((i, label))
        except Exception:
            continue
    return items


def _normalize_model_for_provider(provider: str, model: str) -> str:
    """Normalize model id based on provider expectations.

    - openrouter expects provider/model (e.g., 'anthropic/claude-sonnet-4.5').
    - anthropic expects plain ids (e.g., 'claude-4.5-sonnet').
    """
    prov = (provider or "openrouter").strip().lower()
    m = (model or "").strip()
    if prov == "openrouter":
        if "/" not in m:
            ml = m.lower()
            if ml in {"claude-4.5-sonnet", "sonnet-4.5", "claude-sonnet-4.5"}:
                return "anthropic/claude-sonnet-4.5"
        return m or "anthropic/claude-sonnet-4.5"
    else:  # anthropic
        if "/" in m:
            ml = m.lower()
            if ml in {"anthropic/claude-sonnet-4.5"}:
                return "claude-4.5-sonnet"
        return m or "claude-4.5-sonnet"


def _provider_label(provider: str) -> str:
    p = (provider or "").strip().lower()
    if p == "anthropic":
        return "Anthropic"
    if p == "openrouter":
        return "OpenRouter"
    return "LLM"


def resolve_prompt_params(cfg: Dict, prompt_index: Optional[int] = None) -> Dict:
    """Resolve provider/api_key/model/system_prompt and numeric params.

    Applies per-prompt overrides when cfg['llm_per_prompt_overrides'] is True.
    Environment variables are considered for api keys.

    Returns dict with keys:
      provider, provider_label, api_key, model, system_prompt,
      max_tokens, temperature, timeout_seconds, retry_count
    """
    ensure_llm_config(cfg)

    provider = str(cfg.get("llm_provider", "openrouter")).strip().lower()
    provider_label = _provider_label(provider)

    # Base model
    base_model = str(cfg.get("anthropic_model", "anthropic/claude-sonnet-4.5"))
    # Active prompt selection
    try:
        idx = int(cfg.get("llm_prompt_active", 0)) if prompt_index is None else int(prompt_index)
    except Exception:
        idx = 0
    idx = _clamp_index(idx)
    prompt_item = cfg.get("llm_prompts", [{}])[idx] if isinstance(cfg.get("llm_prompts"), list) else {}
    system_prompt = str((prompt_item or {}).get("text", "")) or str(cfg.get("anthropic_prompt", ""))

    # Overrides
    use_overrides = bool(cfg.get("llm_per_prompt_overrides", False))
    ov = (prompt_item or {}).get("overrides", {}) if isinstance(prompt_item, dict) else {}
    if not isinstance(ov, dict):
        ov = {}

    model = str(ov.get("model", base_model) if use_overrides else base_model)
    model = _normalize_model_for_provider(provider, model)

    def _num(name: str, default_val):
        if use_overrides and name in ov:
            try:
                return type(default_val)(ov.get(name))
            except Exception:
                return default_val
        return type(default_val)(cfg.get(f"anthropic_{name}", default_val))

    max_tokens = _num("max_tokens", 2048)
    temperature = _num("temperature", 0.2)
    timeout_seconds = _num("timeout_seconds", 60)
    retry_count = _num("retry_count", 10)

    # API key resolution
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY") or str(cfg.get("openrouter_api_key", ""))
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or str(cfg.get("anthropic_api_key", ""))

    return {
        "provider": provider,
        "provider_label": provider_label,
        "api_key": api_key or "",
        "model": model,
        "system_prompt": system_prompt,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "timeout_seconds": int(timeout_seconds),
        "retry_count": int(retry_count),
        "active_index": idx,
    }


def build_overrides_for_prompt(cfg: Dict, prompt_index: Optional[int] = None) -> Dict:
    """Build llm_overrides dict suitable for converter's YouTube flow.

    Includes 'system_prompt' always, and when per-prompt overrides are enabled,
    propagates numeric overrides and model if present.
    """
    ensure_llm_config(cfg)
    try:
        idx = int(cfg.get("llm_prompt_active", 0)) if prompt_index is None else int(prompt_index)
    except Exception:
        idx = 0
    idx = _clamp_index(idx)

    prompts = cfg.get("llm_prompts", [])
    item = prompts[idx] if isinstance(prompts, list) else {}
    ov = {}
    if bool(cfg.get("llm_per_prompt_overrides", False)):
        raw = (item or {}).get("overrides", {}) or {}
        if isinstance(raw, dict):
            # Only copy supported keys if present
            for k in ("model", "max_tokens", "temperature", "timeout_seconds", "retry_count"):
                if k in raw and raw.get(k) not in (None, ""):
                    ov[k] = raw.get(k)
    ov["system_prompt"] = str((item or {}).get("text", ""))
    return ov


def sync_legacy_prompt(cfg: Dict) -> None:
    """Keep legacy 'anthropic_prompt' in sync with the active prompt's text."""
    ensure_llm_config(cfg)
    try:
        idx = int(cfg.get("llm_prompt_active", 0))
    except Exception:
        idx = 0
    idx = _clamp_index(idx)
    try:
        prompts = cfg.get("llm_prompts", [])
        active_text = prompts[idx]["text"] if prompts else ""
    except Exception:
        active_text = ""
    cfg["anthropic_prompt"] = str(active_text or "")

