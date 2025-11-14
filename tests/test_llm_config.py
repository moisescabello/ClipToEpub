import os
from typing import Dict, Any

from cliptoepub import llm_config


def _base_cfg() -> Dict[str, Any]:
    return {
        "llm_prompts": [],
        "llm_prompt_active": 0,
        "llm_per_prompt_overrides": False,
    }


def test_ensure_llm_config_populates_defaults_and_migrates_legacy_prompt() -> None:
    cfg = {"anthropic_prompt": "Legacy prompt text"}
    result = llm_config.ensure_llm_config(cfg)

    assert "llm_prompts" in result
    assert len(result["llm_prompts"]) == llm_config.PROMPT_SLOTS
    assert result["llm_prompts"][0]["text"] == "Legacy prompt text"
    assert result["llm_prompt_active"] == 0
    assert result["llm_per_prompt_overrides"] is False


def test_ensure_llm_config_normalizes_existing_prompts_and_index() -> None:
    cfg = {
        "llm_prompts": [{"name": "One", "text": "Prompt 1"}],
        "llm_prompt_active": 10,
        "llm_per_prompt_overrides": "yes",
    }
    result = llm_config.ensure_llm_config(cfg)

    assert len(result["llm_prompts"]) == llm_config.PROMPT_SLOTS
    assert result["llm_prompts"][0]["name"] == "One"
    assert result["llm_prompts"][0]["text"] == "Prompt 1"
    assert isinstance(result["llm_prompts"][0]["overrides"], dict)
    assert result["llm_prompt_active"] == 0
    assert result["llm_per_prompt_overrides"] is True


def test_get_prompt_menu_items_skips_empty_and_uses_fallback_labels() -> None:
    cfg = _base_cfg()
    cfg["llm_prompts"] = [
        {"name": "First", "text": "Prompt 1", "overrides": {}},
        {"name": "", "text": "Prompt 2", "overrides": {}},
        {"name": "", "text": "", "overrides": {}},
    ]

    items = llm_config.get_prompt_menu_items(cfg)

    assert items == [(0, "First"), (1, "Prompt 2")]


def test_resolve_prompt_params_uses_env_keys_and_normalizes_model_anthropic(monkeypatch) -> None:
    cfg: Dict[str, Any] = _base_cfg()
    cfg.update(
        {
            "llm_provider": "anthropic",
            "anthropic_model": "anthropic/claude-sonnet-4.5",
            "llm_prompts": [{"name": "P1", "text": "System", "overrides": {}}],
        }
    )

    monkeypatch = monkeypatch  # type: ignore[assignment]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

    params = llm_config.resolve_prompt_params(cfg)

    assert params["provider"] == "anthropic"
    assert params["provider_label"] == "Anthropic"
    assert params["api_key"] == "env-key"
    assert params["model"] == "claude-4.5-sonnet"
    assert params["system_prompt"] == "System"
    assert params["active_index"] == 0


def test_resolve_prompt_params_applies_per_prompt_overrides(monkeypatch) -> None:
    cfg: Dict[str, Any] = {
        "llm_provider": "openrouter",
        "anthropic_model": "anthropic/claude-sonnet-4.5",
        "llm_per_prompt_overrides": True,
        "llm_prompt_active": 1,
        "llm_prompts": [
            {"name": "P1", "text": "First", "overrides": {}},
            {
                "name": "P2",
                "text": "Second",
                "overrides": {
                    "model": "custom-model",
                    "max_tokens": 4096,
                    "temperature": 0.5,
                    "timeout_seconds": 30,
                    "retry_count": 3,
                },
            },
        ],
    }

    monkeypatch = monkeypatch  # type: ignore[assignment]
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    params = llm_config.resolve_prompt_params(cfg)

    assert params["provider"] == "openrouter"
    assert params["model"] == "custom-model"
    assert params["max_tokens"] == 4096
    assert params["temperature"] == 0.5
    assert params["timeout_seconds"] == 30
    assert params["retry_count"] == 3
    assert params["system_prompt"] == "Second"
    assert params["active_index"] == 1


def test_build_overrides_for_prompt_includes_numeric_overrides_when_enabled() -> None:
    cfg: Dict[str, Any] = _base_cfg()
    cfg.update(
        {
            "llm_per_prompt_overrides": True,
            "llm_prompt_active": 0,
            "llm_prompts": [
                {
                    "name": "Prompt",
                    "text": "System text",
                    "overrides": {
                        "model": "override-model",
                        "max_tokens": 1024,
                        "temperature": 0.9,
                        "timeout_seconds": 20,
                        "retry_count": 2,
                        "ignored_key": "value",
                    },
                }
            ],
        }
    )

    ov = llm_config.build_overrides_for_prompt(cfg)

    assert ov["system_prompt"] == "System text"
    assert ov["model"] == "override-model"
    assert ov["max_tokens"] == 1024
    assert ov["temperature"] == 0.9
    assert ov["timeout_seconds"] == 20
    assert ov["retry_count"] == 2
    assert "ignored_key" not in ov


def test_build_overrides_for_prompt_only_sets_system_prompt_when_disabled() -> None:
    cfg: Dict[str, Any] = _base_cfg()
    cfg.update(
        {
            "llm_per_prompt_overrides": False,
            "llm_prompts": [
                {"name": "Prompt", "text": "System text", "overrides": {"max_tokens": 999}}
            ],
        }
    )

    ov = llm_config.build_overrides_for_prompt(cfg)

    assert ov == {"system_prompt": "System text"}


def test_sync_legacy_prompt_tracks_active_prompt_text() -> None:
    cfg: Dict[str, Any] = {
        "llm_prompts": [
            {"name": "P1", "text": "First", "overrides": {}},
            {"name": "P2", "text": "Second", "overrides": {}},
        ],
        "llm_prompt_active": 1,
    }

    llm_config.sync_legacy_prompt(cfg)

    assert cfg["anthropic_prompt"] == "Second"

