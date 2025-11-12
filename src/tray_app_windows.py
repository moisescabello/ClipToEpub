#!/usr/bin/env python3
"""
Windows System Tray application for ClipToEpub

Implements a QSystemTrayIcon with menu actions, using the unified converter
for hotkeys and conversions. Configuration and history paths are shared via
src/paths.py to keep parity with macOS.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

# Ensure running on Windows
if not sys.platform.startswith("win"):
    # Avoid importing Qt on non-Windows environments
    if __name__ == "__main__":
        print("This tray application is intended for Windows.")
        sys.exit(0)

try:
    from PySide6.QtGui import QIcon, QAction
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    from PySide6.QtCore import QTimer
    HAVE_QT = True
except Exception as e:
    HAVE_QT = False

# When executed directly (python src/tray_app_windows.py), src/ is on sys.path
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore
try:
    from src.converter import ClipboardToEpubConverter  # type: ignore
except Exception:
    from converter import ClipboardToEpubConverter  # type: ignore


DEFAULT_CONFIG = {
    "output_directory": str(paths.get_default_output_dir()),
    "hotkey": "ctrl+shift+e" if sys.platform.startswith("win") else "cmd+shift+e",
    "author": "Unknown Author",
    "language": "en",
    "style": "default",
    "auto_open": False,
    "show_notifications": True,
    "chapter_words": 5000,
    # YouTube subtitles
    "youtube_lang_1": "en",
    "youtube_lang_2": "es",
    "youtube_lang_3": "pt",
    "youtube_prefer_native": True,
    # LLM defaults
    "anthropic_api_key": "",
    # Default model for OpenRouter (Sonnet 4.5 – 1M)
    "anthropic_model": "anthropic/claude-sonnet-4.5",
    "anthropic_prompt": "",
    "anthropic_max_tokens": 2048,
    "anthropic_temperature": 0.2,
    "anthropic_timeout_seconds": 60,
    "anthropic_retry_count": 10,
    "anthropic_hotkey": "ctrl+shift+l" if sys.platform.startswith("win") else "cmd+shift+l",
    # Provider selection and OpenRouter key
    "llm_provider": "openrouter",
    "openrouter_api_key": "",
}


def load_config() -> dict:
    cfg_path = paths.get_config_path()
    try:
        paths.migrate_legacy_paths()
    except (OSError, IOError) as e:
        print(f"Warning: Could not migrate legacy paths: {e}")
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not load config: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    cfg_path = paths.get_config_path()
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except (OSError, IOError, PermissionError) as e:
        print(f"Error: Could not save config: {e}")


def parse_hotkey_string(text: Optional[str]):
    """Convert a hotkey like 'ctrl+shift+e' into a pynput combo set."""
    from pynput import keyboard

    if not text:
        return None

    parts = [p.strip().lower() for p in text.split('+') if p.strip()]
    combo = set()
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


class WindowsTrayApp:
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Tray icon
        self.tray = QSystemTrayIcon()
        try:
            icon_path = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
            if icon_path.exists():
                self.tray.setIcon(QIcon(str(icon_path)))
        except (OSError, RuntimeError) as e:
            # Icon loading failed - not critical
            pass

        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        # Load config and build converter
        self.config = load_config()
        self.converter: Optional[ClipboardToEpubConverter] = None
        self.converter_thread: Optional[threading.Thread] = None
        self._build_converter()

        # Populate menu
        self._build_menu()

        # Show tray icon
        self.tray.setVisible(True)

        # Periodically refresh the recent submenu
        self._recent_timer = QTimer()
        self._recent_timer.setInterval(5000)
        self._recent_timer.timeout.connect(self._refresh_recent_menu)
        self._recent_timer.start()

        # LLM hotkey listener
        self.llm_listener = None
        self.llm_current_keys = set()
        self._setup_llm_hotkey()

    # ---- Converter ----
    def _build_converter(self):
        hotkey_combo = parse_hotkey_string(self.config.get("hotkey"))
        try:
            self.converter = ClipboardToEpubConverter(
                output_dir=self.config["output_directory"],
                default_author=self.config["author"],
                default_language=self.config["language"],
                default_style=self.config["style"],
                chapter_words=self.config["chapter_words"],
                hotkey_combo=hotkey_combo,
                # YouTube + LLM config
                youtube_langs=[
                    str(self.config.get("youtube_lang_1", "en")),
                    str(self.config.get("youtube_lang_2", "es")),
                    str(self.config.get("youtube_lang_3", "pt")),
                ],
                youtube_prefer_native=bool(self.config.get("youtube_prefer_native", True)),
                llm_provider=str(self.config.get("llm_provider", "openrouter")),
                anthropic_api_key=str(self.config.get("anthropic_api_key", "")),
                openrouter_api_key=str(self.config.get("openrouter_api_key", "")),
                anthropic_model=str(self.config.get("anthropic_model", "anthropic/claude-sonnet-4.5")),
                anthropic_prompt=str(self.config.get("anthropic_prompt", "")),
                anthropic_max_tokens=int(self.config.get("anthropic_max_tokens", 2048)),
                anthropic_temperature=float(self.config.get("anthropic_temperature", 0.2)),
                anthropic_timeout_seconds=int(self.config.get("anthropic_timeout_seconds", 60)),
                anthropic_retry_count=int(self.config.get("anthropic_retry_count", 10)),
            )
            # Attach callback for conversions
            def on_conversion(filepath: str):
                if filepath and self.config.get("show_notifications", True):
                    self.tray.showMessage("ePub Created", os.path.basename(filepath))
                # Auto-open
                if filepath and self.config.get("auto_open", False):
                    try:
                        os.startfile(filepath)  # type: ignore[attr-defined]
                    except (OSError, AttributeError) as e:
                        print(f"Warning: Could not open file: {e}")
                # Force a recent menu refresh soon
                QTimer.singleShot(250, self._refresh_recent_menu)

            self.converter.conversion_callback = on_conversion
        except Exception as e:
            # Minimal fallback
            print(f"Error creating converter: {e}")

    def _start_listener_thread(self):
        if not self.converter or self.converter_thread:
            return

        def run():
            try:
                self.converter.start_listening()
            except Exception as e:
                print(f"Listener error: {e}")

        self.converter_thread = threading.Thread(target=run, daemon=True)
        self.converter_thread.start()

    # ---- UI / Menu ----
    def _build_menu(self):
        self.menu.clear()

        # Convert now
        action_convert = QAction("Convert Now", self.menu)
        action_convert.triggered.connect(self._convert_now)
        self.menu.addAction(action_convert)

        # Convert with LLM
        action_convert_llm = QAction("Convert with LLM", self.menu)
        action_convert_llm.triggered.connect(self._convert_with_llm)
        self.menu.addAction(action_convert_llm)

        self.menu.addSeparator()

        # Open output folder
        action_open_folder = QAction("Open ePubs Folder", self.menu)
        action_open_folder.triggered.connect(self._open_folder)
        self.menu.addAction(action_open_folder)

        # Recent submenu
        self.recent_menu = self.menu.addMenu("Recent Conversions")
        self._populate_recent_menu()

        self.menu.addSeparator()

        # Toggles
        self.action_auto_open = QAction("Auto-open after creation", self.menu)
        self.action_auto_open.setCheckable(True)
        self.action_auto_open.setChecked(bool(self.config.get("auto_open", False)))
        self.action_auto_open.triggered.connect(self._toggle_auto_open)
        self.menu.addAction(self.action_auto_open)

        self.action_notifications = QAction("Show notifications", self.menu)
        self.action_notifications.setCheckable(True)
        self.action_notifications.setChecked(bool(self.config.get("show_notifications", True)))
        self.action_notifications.triggered.connect(self._toggle_notifications)
        self.menu.addAction(self.action_notifications)

        # Settings
        action_settings = QAction("Settings…", self.menu)
        action_settings.triggered.connect(self._open_settings)
        self.menu.addAction(action_settings)

        # Quit
        self.menu.addSeparator()
        action_quit = QAction("Quit", self.menu)
        action_quit.triggered.connect(self._quit)
        self.menu.addAction(action_quit)

        # Start listener last
        self._start_listener_thread()
        # Ensure LLM listener is running
        self._setup_llm_hotkey()

    def _populate_recent_menu(self):
        self.recent_menu.clear()
        out_dir = Path(self.config.get("output_directory", paths.get_default_output_dir()))
        if not out_dir.exists():
            self.recent_menu.addAction("No recent conversions")
            return

        files = sorted(out_dir.glob("*.epub"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        if not files:
            self.recent_menu.addAction("No recent conversions")
            return

        for p in files:
            act = QAction(p.name, self.recent_menu)
            act.triggered.connect(lambda _=False, path=str(p): self._open_file(path))
            self.recent_menu.addAction(act)

    def _refresh_recent_menu(self):
        self._populate_recent_menu()

    # ---- Actions ----
    def _convert_now(self):
        if not self.converter:
            return
        try:
            path = self.converter.convert_clipboard_content()
            if path and self.config.get("show_notifications", True):
                self.tray.showMessage("ePub Created", os.path.basename(path))
            if path and self.config.get("auto_open", False):
                try:
                    os.startfile(path)  # type: ignore[attr-defined]
                except (OSError, AttributeError) as e:
                    print(f"Warning: Could not open file: {e}")
        except Exception as e:
            self.tray.showMessage("Error", f"Conversion failed: {e}")

    def _open_folder(self):
        folder = self.config.get("output_directory", str(paths.get_default_output_dir()))
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)  # type: ignore[attr-defined]
        except (OSError, AttributeError) as e:
            print(f"Warning: Could not open folder: {e}")

    def _open_file(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)  # type: ignore[attr-defined]
        except (OSError, AttributeError) as e:
            print(f"Warning: Could not open file: {e}")

    def _toggle_auto_open(self):
        self.config["auto_open"] = not bool(self.config.get("auto_open", False))
        save_config(self.config)

    def _toggle_notifications(self):
        self.config["show_notifications"] = not bool(self.config.get("show_notifications", True))
        save_config(self.config)

    def _open_settings(self):
        # Try Qt settings window first
        base_dir = Path(__file__).resolve().parent
        qt_path = base_dir / "config_window_qt.py"
        tk_path = base_dir / "config_window.py"

        try:
            import subprocess

            def run(p: Path):
                return subprocess.run([sys.executable, str(p)], capture_output=True, text=True)

            res = None
            if qt_path.exists():
                res = run(qt_path)
                if res.returncode != 0 and tk_path.exists():
                    res = run(tk_path)
            elif tk_path.exists():
                res = run(tk_path)

            # Reload config and rebuild converter
            self.config = load_config()
            self._build_converter()
            self._build_menu()
            self._setup_llm_hotkey()

            # Optional feedback
            if res and res.returncode != 0:
                self.tray.showMessage("Settings", "Settings window reported an error; changes may not apply.")
        except Exception as e:
            self.tray.showMessage("Settings", f"Could not open settings: {e}")

    def _quit(self):
        try:
            if self.converter:
                self.converter.stop_listening()
            if self.llm_listener:
                try:
                    self.llm_listener.stop()
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Error stopping converter on quit: {e}")
        QApplication.quit()

    # ---- LLM ----
    def _convert_with_llm(self):
        if not self.converter:
            return
        try:
            # If clipboard contains a YouTube URL, delegate to converter's pipeline
            def _looks_like_youtube_url(text: str) -> bool:
                try:
                    from urllib.parse import urlparse
                    t = (text or "").strip()
                    if not t or "\n" in t:
                        return False
                    u = urlparse(t)
                    if u.scheme not in ("http", "https"):
                        return False
                    host = (u.netloc or "").lower()
                    return ("youtube.com" in host) or ("youtu.be" in host)
                except Exception:
                    return False

            import pyperclip
            clip_text = pyperclip.paste() or ""
            if clip_text and _looks_like_youtube_url(str(clip_text)):
                def run_youtube():
                    try:
                        path = self.converter.convert_clipboard_content() if self.converter else None
                        if path:
                            if self.config.get("show_notifications", True):
                                self.tray.showMessage("ePub Created", os.path.basename(path))
                            if self.config.get("auto_open", False):
                                try:
                                    os.startfile(path)  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                        else:
                            self.tray.showMessage("Conversion Error", "Could not create ePub from YouTube subtitles")
                    except Exception as e:
                        self.tray.showMessage("LLM Error", str(e))

                threading.Thread(target=run_youtube, daemon=True).start()
                return

            provider = str(self.config.get("llm_provider", "anthropic")).strip().lower()
            if provider == "openrouter":
                api_key = os.environ.get("OPENROUTER_API_KEY") or str(self.config.get("openrouter_api_key", ""))
                model = str(self.config.get("anthropic_model", "anthropic/claude-sonnet-4.5")) or "anthropic/claude-sonnet-4.5"
                if "/" not in model:
                    if model.lower() in {"claude-4.5-sonnet", "claude-sonnet-4.5", "sonnet-4.5"}:
                        model = "anthropic/claude-sonnet-4.5"
            else:
                api_key = os.environ.get("ANTHROPIC_API_KEY") or str(self.config.get("anthropic_api_key", ""))
                model = str(self.config.get("anthropic_model", "claude-4.5-sonnet")) or "claude-4.5-sonnet"
                if "/" in model:
                    if model.lower() in {"anthropic/claude-sonnet-4.5"}:
                        model = "claude-4.5-sonnet"
            prompt = str(self.config.get("anthropic_prompt", ""))
            max_tokens = int(self.config.get("anthropic_max_tokens", 2048))
            temperature = float(self.config.get("anthropic_temperature", 0.2))
            timeout_s = int(self.config.get("anthropic_timeout_seconds", 60))
            retries = int(self.config.get("anthropic_retry_count", 10))

            if not api_key or not prompt:
                self.tray.showMessage("Anthropic", "Configure API Key and Prompt in Settings")
                return

            if not clip_text.strip():
                self.tray.showMessage("No Content", "Clipboard is empty or contains no text")
                return

            def run():
                try:
                    try:
                        from src.llm_anthropic import process_text, sanitize_first_line  # type: ignore
                    except Exception:
                        from llm_anthropic import process_text, sanitize_first_line  # type: ignore

                    md = process_text(
                        str(clip_text),
                        api_key=str(api_key),
                        model=str(model),
                        system_prompt=str(prompt),
                        max_tokens=int(max_tokens),
                        temperature=float(temperature),
                        timeout_s=int(timeout_s),
                        retries=int(retries),
                    )

                    title = sanitize_first_line(md)
                    path = self.converter.convert_text_to_epub(md, suggested_title=title, tags=["anthropic"]) if self.converter else None
                    if path:
                        if self.config.get("show_notifications", True):
                            self.tray.showMessage("ePub Created", os.path.basename(path))
                        if self.config.get("auto_open", False):
                            try:
                                os.startfile(path)  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    else:
                        self.tray.showMessage("Conversion Error", "Could not create ePub from LLM output")
                except Exception as e:
                    self.tray.showMessage("LLM Error", str(e))

            t = threading.Thread(target=run, daemon=True)
            t.start()
        except Exception as e:
            self.tray.showMessage("Error", f"LLM conversion failed: {e}")

    def _setup_llm_hotkey(self):
        try:
            from pynput import keyboard
        except Exception as e:
            print(f"LLM hotkey setup skipped: {e}")
            return

        combo = parse_hotkey_string(self.config.get("anthropic_hotkey")) or set()
        self.llm_hotkey = combo

        def on_press(key):
            self.llm_current_keys.add(key)
            if self.llm_hotkey and self.llm_hotkey.issubset(self.llm_current_keys):
                self._convert_with_llm()

        def on_release(key):
            try:
                self.llm_current_keys.remove(key)
            except KeyError:
                pass

        try:
            if self.llm_listener:
                self.llm_listener.stop()
            self.llm_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.llm_listener.start()
        except Exception as e:
            print(f"LLM hotkey listener error: {e}")


def main():
    if not sys.platform.startswith("win"):
        print("This tray application is intended for Windows.")
        return 0
    if not HAVE_QT:
        print("PySide6 is not available. Please install PySide6 to run the tray app.")
        return 1
    app = WindowsTrayApp()
    return app.app.exec()


if __name__ == "__main__":
    sys.exit(main())
