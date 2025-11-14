#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class ErrorEvent:
    title: str
    message: str
    severity: str = "error"  # one of: info, warning, error
    context: Optional[Dict[str, Any]] = None


class ErrorCallback(Protocol):
    def __call__(self, event: ErrorEvent | str) -> None: ...


def notify_error(cb: Optional[ErrorCallback], title: str, message: str, *, severity: str = "error", context: Optional[Dict[str, Any]] = None) -> None:
    """Invoke an error callback in a backward-compatible way.

    If a structured callback is provided, send an ErrorEvent; otherwise fall back to a simple
    string payload of the form "<title>: <message>".
    """
    if not cb:
        return
    event = ErrorEvent(title=title, message=message, severity=severity, context=context)
    try:
        cb(event)
    except TypeError:
        # Older callbacks may expect a simple string
        try:
            cb(f"{title}: {message}")
        except Exception:
            pass


__all__ = ["ErrorEvent", "ErrorCallback", "notify_error"]

