#!/usr/bin/env python3
"""
Cross‑platform paths and light migration helpers for ClipToEpub.

Centralizes locations for configuration, history and update-check files.
On Windows, stores data under %APPDATA%\ClipToEpub. On macOS, keeps the
existing locations for compatibility.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_windows() -> bool:
    return sys.platform.startswith("win")


def _appdata_dir() -> Path:
    """Return %APPDATA% directory on Windows, with a sensible fallback."""
    env = os.environ.get("APPDATA")
    if env:
        return Path(env)
    # Fallback for unusual environments
    return Path.home() / "AppData" / "Roaming"


def get_default_output_dir() -> Path:
    """Default output directory for generated ePubs."""
    return Path.home() / "Documents" / "ClipToEpubs"


def get_config_path() -> Path:
    """Return platform-appropriate configuration file path."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "config.json"
    return Path.home() / "Library" / "Preferences" / "cliptoepub.json"


def get_history_path() -> Path:
    """Return platform-appropriate history file path."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "history.json"
    return Path.home() / ".cliptoepub" / "history.json"


def get_update_check_path() -> Path:
    """Return file used to cache update-check metadata."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "cliptoepub-update.json"
    return Path.home() / "Library" / "Preferences" / "cliptoepub-update.json"


def _safe_move(src: Path, dst: Path) -> bool:
    """Move file from src to dst creating parent directories. Returns True if moved."""
    try:
        if not src.exists() or dst.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def migrate_legacy_paths() -> dict:
    """
    On Windows, migrate files that older versions may have created under Unix-like
    paths in the user profile to the proper %APPDATA% locations.

    Returns a dict with migration results for observability.
    """
    results = {
        "config_migrated": False,
        "history_migrated": False,
        "update_migrated": False,
    }

    if not is_windows():
        return results

    # Known legacy locations that might exist if older code ran on Windows
    legacy_config = Path.home() / "Library" / "Preferences" / "clipboard-to-epub.json"
    legacy_history = Path.home() / ".clipboard_to_epub" / "history.json"
    legacy_update = Path.home() / "Library" / "Preferences" / "clipboard-to-epub-update.json"

    # Target locations
    new_config = get_config_path()
    new_history = get_history_path()
    new_update = get_update_check_path()

    if _safe_move(legacy_config, new_config):
        results["config_migrated"] = True
    if _safe_move(legacy_history, new_history):
        results["history_migrated"] = True
    if _safe_move(legacy_update, new_update):
        results["update_migrated"] = True

    # Ensure directories exist for fresh installs
    for p in (new_config, new_history, new_update):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # Ensure default output directory exists lazily (created by app modules as needed)
    return results

