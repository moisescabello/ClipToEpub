#!/usr/bin/env python3
from __future__ import annotations

"""
Hotkey parsing helpers shared by menubar and tray apps.

Converts strings like "cmd+shift+e" or "ctrl+alt+f2" into pynput key sets.
"""

from typing import Optional, Set


def parse_hotkey_string(text: Optional[str]):
    """Convert a hotkey like 'ctrl+shift+e' into a pynput combo set.

    Returns a set of pynput keyboard keys, or None when input is empty/invalid.
    """
    try:
        from pynput import keyboard
    except Exception:
        return None

    if not text:
        return None

    parts = [p.strip().lower() for p in str(text).split('+') if p.strip()]
    combo: Set[object] = set()
    for p in parts:
        if p in ("ctrl", "control"):
            combo.add(keyboard.Key.ctrl)
        elif p in ("cmd", "command", "meta"):
            combo.add(keyboard.Key.cmd)
        elif p in ("alt", "option"):
            combo.add(keyboard.Key.alt)
        elif p == "shift":
            combo.add(keyboard.Key.shift)
        elif len(p) == 1:
            combo.add(keyboard.KeyCode.from_char(p))
        elif p.startswith('f') and p[1:].isdigit():
            try:
                combo.add(getattr(keyboard.Key, p))
            except AttributeError:
                pass
        elif p in ("space", "tab", "enter", "return", "backspace", "esc", "escape"):
            key_name = "esc" if p == "escape" else ("enter" if p == "return" else p)
            try:
                combo.add(getattr(keyboard.Key, key_name))
            except AttributeError:
                pass
    return combo or None


__all__ = ["parse_hotkey_string"]

