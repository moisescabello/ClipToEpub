#!/usr/bin/env python3
"""
Modern Settings Window (Qt) for Clipboard to ePub
Falls back to Tkinter settings if PySide6 is not available.
Cross-platform friendly. Kept as a separate module to avoid impacting
current flows; menubar prefers this window when present.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
# Robust import for paths whether run from repo root or src/
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore


def load_config(defaults: dict) -> dict:
    path = paths.get_config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Ensure all defaults are present
            for k, v in defaults.items():
                data.setdefault(k, v)
            return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not load config from {path}: {e}")
            return defaults.copy()
    return defaults.copy()


def save_config(config: dict) -> bool:
    try:
        path = paths.get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return True
    except (OSError, IOError, PermissionError) as e:
        print(f"Error: Could not save config to {path}: {e}")
        return False


# Try importing PySide6; fallback to Tkinter module if missing
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QKeySequence
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QKeySequenceEdit,
        QScrollArea,
        QSpinBox,
        QDoubleSpinBox,
        QTextEdit,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
    HAVE_QT = True
except ImportError as e:
    # PySide6 not installed - will fall back to Tkinter
    print(f"PySide6 not available: {e}")
    HAVE_QT = False


DEFAULT_HOTKEY = "ctrl+shift+e" if sys.platform.startswith("win") else "cmd+shift+e"
DEFAULTS = {
    "output_directory": str(paths.get_default_output_dir()),
    "hotkey": DEFAULT_HOTKEY,
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
    "llm_provider": "openrouter",  # 'anthropic' | 'openrouter'
    "openrouter_api_key": "",
}


def list_available_styles() -> list[str]:
    styles = {"default", "minimal", "modern"}
    try:
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        if templates_dir.exists():
            for p in templates_dir.glob("*.css"):
                styles.add(p.stem)
    except (OSError, RuntimeError) as e:
        print(f"Warning: Could not scan templates directory: {e}")
        # Return default styles only
    return sorted(styles)


if HAVE_QT:
    def _normalize_for_qt(seq_text: str) -> str:
        # Convert stored format like 'cmd+shift+e' to Qt-friendly 'Meta+Shift+E'
        if not seq_text:
            return ""
        parts = [p.strip().lower() for p in seq_text.split("+") if p.strip()]
        out: list[str] = []
        for p in parts:
            if p in ("cmd", "command", "meta"):
                out.append("Meta")
            elif p in ("ctrl", "control"):
                out.append("Ctrl")
            elif p == "shift":
                out.append("Shift")
            elif p in ("alt", "option"):
                out.append("Alt")
            else:
                out.append(p.upper())
        return "+".join(out)

    def _normalize_from_qt(seq: QKeySequence) -> str:
        # Convert Qt sequence to portable lower-case like 'cmd+shift+e' on mac, 'ctrl+shift+e' otherwise
        if not seq or seq.isEmpty():
            return DEFAULTS["hotkey"]
        text = seq.toString(QKeySequence.PortableText)  # e.g., 'Meta+Shift+E'
        parts = [p.strip().lower() for p in text.split("+") if p.strip()]
        out: list[str] = []
        for p in parts:
            if p == "meta":
                out.append("cmd")
            else:
                out.append(p)
        return "+".join(out)

    class SettingsDialog(QDialog):
        def __init__(self, config: dict, parent: QWidget | None = None):
            super().__init__(parent)
            self.setWindowTitle("Clipboard to ePub – Settings")
            self.setMinimumSize(640, 520)
            self.config = config

            # Window icon (optional)
            try:
                icon_path = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
                if icon_path.exists():
                    self.setWindowIcon(QIcon(str(icon_path)))
            except (OSError, RuntimeError) as e:
                # Icon loading failed - not critical
                print(f"Warning: Could not load window icon: {e}")

            # Main layout with tabs inside a scroll area per tab if needed
            layout = QVBoxLayout(self)
            self.tabs = QTabWidget(self)
            layout.addWidget(self.tabs)

            # Tabs (wrapped in scroll areas to avoid clipping on small screens)
            self._setup_general_tab()
            self._setup_appearance_tab()
            self._setup_advanced_tab()
            self._setup_llm_tab()

            # Buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
            )
            self.button_box.accepted.connect(self.on_save)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)

        # ---- Tabs ----
        def _setup_general_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Output directory (line edit + browse)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            self.output_edit = QLineEdit(self.config["output_directory"])
            browse_btn = QPushButton("Browse…")
            browse_btn.clicked.connect(self._browse_output)
            row_layout.addWidget(self.output_edit)
            row_layout.addWidget(browse_btn)
            form.addRow("Output Directory:", row)

            # Hotkey (capture)
            hotkey_row = QWidget()
            hotkey_layout = QHBoxLayout(hotkey_row)
            self.hotkey_edit = QKeySequenceEdit()
            try:
                qt_seq = QKeySequence(_normalize_for_qt(self.config.get("hotkey", DEFAULTS["hotkey"])) )
                self.hotkey_edit.setKeySequence(qt_seq)
            except Exception:
                # Fallback to default
                self.hotkey_edit.setKeySequence(QKeySequence(_normalize_for_qt(DEFAULTS["hotkey"])) )
            reset_hotkey_btn = QPushButton("Reset")
            def _reset_hotkey():
                self.hotkey_edit.setKeySequence(QKeySequence(_normalize_for_qt(DEFAULTS["hotkey"])) )
            reset_hotkey_btn.clicked.connect(_reset_hotkey)
            hotkey_layout.addWidget(self.hotkey_edit, stretch=1)
            hotkey_layout.addWidget(reset_hotkey_btn)
            form.addRow("Capture Hotkey:", hotkey_row)

            # Author
            self.author_edit = QLineEdit(self.config["author"])
            form.addRow("Default Author:", self.author_edit)

            # Language
            self.language_combo = QComboBox()
            self.language_combo.addItems(["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko"])
            current_lang = self.config.get("language", "en")
            idx = self.language_combo.findText(current_lang)
            if idx >= 0:
                self.language_combo.setCurrentIndex(idx)
            form.addRow("Language:", self.language_combo)

            # YouTube subtitles preferences
            yt_group = QGroupBox("YouTube Subtitles")
            yt_layout = QGridLayout(yt_group)
            yt_langs = [
                ("en", "English"),
                ("es", "Spanish"),
                ("pt", "Portuguese"),
                ("hi", "Hindi"),
                ("id", "Indonesian"),
                ("ar", "Arabic"),
                ("ru", "Russian"),
                ("ja", "Japanese"),
                ("ko", "Korean"),
                ("fr", "French"),
                ("de", "German"),
                ("tr", "Turkish"),
            ]
            self.yt_lang1 = QComboBox(); self.yt_lang2 = QComboBox(); self.yt_lang3 = QComboBox()
            for code, label in yt_langs:
                disp = f"{code} – {label}"
                self.yt_lang1.addItem(disp, userData=code)
                self.yt_lang2.addItem(disp, userData=code)
                self.yt_lang3.addItem(disp, userData=code)
            # Set current selections
            def _set_combo(combo: QComboBox, code: str):
                for i in range(combo.count()):
                    if str(combo.itemData(i)) == str(code):
                        combo.setCurrentIndex(i)
                        return
            _set_combo(self.yt_lang1, str(self.config.get("youtube_lang_1", "en")))
            _set_combo(self.yt_lang2, str(self.config.get("youtube_lang_2", "es")))
            _set_combo(self.yt_lang3, str(self.config.get("youtube_lang_3", "pt")))
            self.yt_prefer_native = QCheckBox("Prefer native subtitles; fallback to auto-generated")
            self.yt_prefer_native.setChecked(bool(self.config.get("youtube_prefer_native", True)))

            yt_layout.addWidget(QLabel("Preferred language 1:"), 0, 0)
            yt_layout.addWidget(self.yt_lang1, 0, 1)
            yt_layout.addWidget(QLabel("Preferred language 2:"), 1, 0)
            yt_layout.addWidget(self.yt_lang2, 1, 1)
            yt_layout.addWidget(QLabel("Preferred language 3:"), 2, 0)
            yt_layout.addWidget(self.yt_lang3, 2, 1)
            yt_layout.addWidget(self.yt_prefer_native, 3, 0, 1, 2)
            form.addRow(yt_group)

            # Toggles
            self.auto_open_chk = QCheckBox("Auto-open ePub files after creation")
            self.auto_open_chk.setChecked(bool(self.config.get("auto_open", False)))
            self.notifications_chk = QCheckBox("Show notifications")
            self.notifications_chk.setChecked(bool(self.config.get("show_notifications", True)))
            form.addRow(self.auto_open_chk)
            form.addRow(self.notifications_chk)

            # Wrap in scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "General")

        def _setup_appearance_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # CSS Style
            self.style_combo = QComboBox()
            for s in list_available_styles():
                self.style_combo.addItem(s)
            cur_style = self.config.get("style", "default")
            idx = self.style_combo.findText(cur_style)
            if idx >= 0:
                self.style_combo.setCurrentIndex(idx)
            form.addRow("CSS Style:", self.style_combo)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "Appearance")

        def _setup_advanced_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Chapter words
            self.chapter_spin = QSpinBox()
            self.chapter_spin.setRange(100, 50000)
            self.chapter_spin.setSingleStep(500)
            self.chapter_spin.setValue(int(self.config.get("chapter_words", 5000)))
            form.addRow("Words per Chapter:", self.chapter_spin)

            # Info
            cfg_path_text = str(paths.get_config_path())
            info = QLabel(
                f"Config Location: {cfg_path_text}\n"
                f"Current Hotkey: {self.config.get('hotkey', DEFAULTS['hotkey']).upper()}"
            )
            info.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(info)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "Advanced")

        def _setup_llm_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Provider selection
            self.provider_combo = QComboBox()
            self.provider_combo.addItem("Anthropic (Sonnet 4.5)", userData="anthropic")
            self.provider_combo.addItem("OpenRouter (Sonnet 4.5 – 1M)", userData="openrouter")
            try:
                # Set initial provider
                cur = str(self.config.get("llm_provider", DEFAULTS["llm_provider"]))
                for i in range(self.provider_combo.count()):
                    if self.provider_combo.itemData(i) == cur:
                        self.provider_combo.setCurrentIndex(i)
                        break
            except Exception:
                pass
            form.addRow("Provider:", self.provider_combo)

            # API Key (masked)
            self.anthropic_key_edit = QLineEdit(self.config.get("anthropic_api_key", ""))
            self.anthropic_key_edit.setEchoMode(QLineEdit.Password)
            form.addRow("Anthropic API Key:", self.anthropic_key_edit)

            # OpenRouter API Key (masked)
            self.openrouter_key_edit = QLineEdit(self.config.get("openrouter_api_key", ""))
            self.openrouter_key_edit.setEchoMode(QLineEdit.Password)
            form.addRow("OpenRouter API Key:", self.openrouter_key_edit)

            # Model
            self.anthropic_model_edit = QLineEdit(self.config.get("anthropic_model", DEFAULTS["anthropic_model"]))
            try:
                self.anthropic_model_edit.setPlaceholderText("e.g., claude-4.5-sonnet or anthropic/claude-sonnet-4.5")
            except Exception:
                pass
            form.addRow("Model:", self.anthropic_model_edit)

            # Model preset (helps set common ids and provider)
            try:
                self.model_preset_combo = QComboBox()
                self.model_preset_combo.addItem("— Select preset —", userData="")
                self.model_preset_combo.addItem("Sonnet 4.5 – OpenRouter (1M)", userData="anthropic/claude-sonnet-4.5")
                self.model_preset_combo.addItem("Sonnet 4.5 – Anthropic", userData="claude-4.5-sonnet")
                self.model_preset_combo.addItem("Mistral Medium 3.1 – OpenRouter (128k)", userData="mistralai/mistral-medium-3.1")
                def _apply_preset(idx: int):
                    val = self.model_preset_combo.itemData(idx)
                    if not val:
                        return
                    try:
                        self.anthropic_model_edit.setText(str(val))
                        # Auto-switch provider based on id format
                        if "/" in str(val):
                            # OpenRouter-style id
                            for i in range(self.provider_combo.count()):
                                if self.provider_combo.itemData(i) == "openrouter":
                                    self.provider_combo.setCurrentIndex(i)
                                    break
                        else:
                            for i in range(self.provider_combo.count()):
                                if self.provider_combo.itemData(i) == "anthropic":
                                    self.provider_combo.setCurrentIndex(i)
                                    break
                    except Exception:
                        pass
                self.model_preset_combo.currentIndexChanged.connect(_apply_preset)
                form.addRow("Preset:", self.model_preset_combo)
            except Exception:
                pass

            # Provider hint for Sonnet 4.5 (1M context via OpenRouter)
            try:
                hint = QLabel("Tip: For Sonnet 4.5 (1M context), switch Provider to OpenRouter, set model 'anthropic/claude-sonnet-4.5' and configure OPENROUTER_API_KEY.")
                hint.setWordWrap(True)
                form.addRow("", hint)
            except Exception:
                pass

            # Prompt (multiline)
            self.anthropic_prompt_edit = QTextEdit(self.config.get("anthropic_prompt", ""))
            self.anthropic_prompt_edit.setPlaceholderText("System prompt to guide the model output (Markdown)")
            form.addRow("System Prompt:", self.anthropic_prompt_edit)

            # Hotkey
            self.anthropic_hotkey_edit = QLineEdit(self.config.get("anthropic_hotkey", DEFAULTS["anthropic_hotkey"]))
            form.addRow("LLM Hotkey:", self.anthropic_hotkey_edit)

            # Numeric params
            self.anthropic_max_tokens_spin = QSpinBox()
            self.anthropic_max_tokens_spin.setRange(1, 200000)
            self.anthropic_max_tokens_spin.setValue(int(self.config.get("anthropic_max_tokens", 2048)))
            form.addRow("Max Tokens:", self.anthropic_max_tokens_spin)

            # Clarification: max_tokens controls output length, not context window
            try:
                note = QLabel("Note: Max Tokens limits output tokens. Context window (input size) depends on the selected model and your account access.")
                note.setWordWrap(True)
                form.addRow("", note)
            except Exception:
                pass

            self.anthropic_temperature_spin = QDoubleSpinBox()
            self.anthropic_temperature_spin.setRange(0.0, 2.0)
            self.anthropic_temperature_spin.setSingleStep(0.1)
            self.anthropic_temperature_spin.setDecimals(2)
            self.anthropic_temperature_spin.setValue(float(self.config.get("anthropic_temperature", 0.2)))
            form.addRow("Temperature:", self.anthropic_temperature_spin)

            self.anthropic_timeout_spin = QSpinBox()
            self.anthropic_timeout_spin.setRange(5, 600)
            self.anthropic_timeout_spin.setValue(int(self.config.get("anthropic_timeout_seconds", 60)))
            form.addRow("Timeout (s):", self.anthropic_timeout_spin)

            self.anthropic_retry_spin = QSpinBox()
            self.anthropic_retry_spin.setRange(0, 20)
            self.anthropic_retry_spin.setValue(int(self.config.get("anthropic_retry_count", 10)))
            form.addRow("Retries:", self.anthropic_retry_spin)

            # Auto-timeout from tokens, preserving manual override
            self._timeout_user_override = False

            def _mark_timeout_override():
                # User edited timeout directly; stop auto-adjusting
                self._timeout_user_override = True

            self.anthropic_timeout_spin.editingFinished.connect(_mark_timeout_override)

            def _recommended_timeout(tokens: int) -> int:
                # Heuristic: ~50 tok/s + 30s buffer; clamp 30..300
                try:
                    v = int(tokens)
                except Exception:
                    v = 0
                rec = int(round(v / 50.0)) + 30
                if rec < 30:
                    rec = 30
                if rec > 300:
                    rec = 300
                return rec

            def _on_tokens_changed(val: int):
                if self._timeout_user_override:
                    return
                # Update timeout programmatically without toggling user intent
                new_timeout = _recommended_timeout(val)
                try:
                    self.anthropic_timeout_spin.blockSignals(True)
                    self.anthropic_timeout_spin.setValue(new_timeout)
                finally:
                    self.anthropic_timeout_spin.blockSignals(False)

            self.anthropic_max_tokens_spin.valueChanged.connect(_on_tokens_changed)

            # Test & Reset buttons
            test_btn = QPushButton("Test Connection")
            def _test():
                try:
                    try:
                        from src.llm_anthropic import process_text  # type: ignore
                    except Exception:
                        from llm_anthropic import process_text  # type: ignore
                    provider = str(self.provider_combo.currentData() or "anthropic")
                    if provider == "openrouter":
                        api_key = self.openrouter_key_edit.text().strip() or os.environ.get("OPENROUTER_API_KEY", "")
                        model = self.anthropic_model_edit.text().strip() or "anthropic/claude-sonnet-4.5"
                    else:
                        api_key = self.anthropic_key_edit.text().strip() or os.environ.get("ANTHROPIC_API_KEY", "")
                        model = self.anthropic_model_edit.text().strip() or DEFAULTS["anthropic_model"]
                    prompt = self.anthropic_prompt_edit.toPlainText().strip() or "Return the input as Markdown."
                    sample = "Test message from Clipboard to ePub"
                    md = process_text(sample, api_key=api_key, model=model, system_prompt=prompt, max_tokens=128, temperature=0.0, timeout_s=30, retries=2)
                    preview = (md or "").strip().splitlines()[0:3]
                    QMessageBox.information(self, "LLM OK", "\n".join(preview) or "Received response")
                except Exception as e:
                    QMessageBox.critical(self, "LLM Error", str(e))
            test_btn.clicked.connect(_test)

            reset_btn = QPushButton("Reset Timeout to Recommended")
            def _reset_timeout():
                try:
                    tokens = int(self.anthropic_max_tokens_spin.value())
                except Exception:
                    tokens = 0
                rec = _recommended_timeout(tokens)
                try:
                    self.anthropic_timeout_spin.blockSignals(True)
                    self.anthropic_timeout_spin.setValue(rec)
                finally:
                    self.anthropic_timeout_spin.blockSignals(False)
                # Re-enable auto adjustments for future token changes
                self._timeout_user_override = False

            reset_btn.clicked.connect(_reset_timeout)

            btn_row = QWidget()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.addWidget(test_btn)
            btn_layout.addWidget(reset_btn)
            form.addRow(btn_row)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "LLM")

        # ---- Actions ----
        def _browse_output(self):
            initial = self.output_edit.text() or str(Path.home())
            folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", initial)
            if folder:
                self.output_edit.setText(folder)

        def on_save(self):
            # Gather values and persist
            cfg = {
                "output_directory": self.output_edit.text().strip() or DEFAULTS["output_directory"],
                "hotkey": _normalize_from_qt(self.hotkey_edit.keySequence()),
                "author": self.author_edit.text().strip() or DEFAULTS["author"],
                "language": self.language_combo.currentText(),
                "style": self.style_combo.currentText(),
                "auto_open": self.auto_open_chk.isChecked(),
                "show_notifications": self.notifications_chk.isChecked(),
                "chapter_words": int(self.chapter_spin.value()),
                # YouTube
                "youtube_lang_1": str(self.yt_lang1.currentData() or "en"),
                "youtube_lang_2": str(self.yt_lang2.currentData() or "es"),
                "youtube_lang_3": str(self.yt_lang3.currentData() or "pt"),
                "youtube_prefer_native": bool(self.yt_prefer_native.isChecked()),
                # LLM
                "llm_provider": str(self.provider_combo.currentData() or DEFAULTS["llm_provider"]),
                "anthropic_api_key": self.anthropic_key_edit.text().strip(),
                "openrouter_api_key": self.openrouter_key_edit.text().strip(),
                "anthropic_model": self.anthropic_model_edit.text().strip() or DEFAULTS["anthropic_model"],
                "anthropic_prompt": self.anthropic_prompt_edit.toPlainText().strip(),
                "anthropic_max_tokens": int(self.anthropic_max_tokens_spin.value()),
                "anthropic_temperature": float(self.anthropic_temperature_spin.value()),
                "anthropic_timeout_seconds": int(self.anthropic_timeout_spin.value()),
                "anthropic_retry_count": int(self.anthropic_retry_spin.value()),
                "anthropic_hotkey": self.anthropic_hotkey_edit.text().strip() or DEFAULTS["anthropic_hotkey"],
            }

            ok = save_config(cfg)
            if ok:
                QMessageBox.information(self, "Settings Saved", "Configuration saved successfully!\n\nRestart the menu bar app to apply changes.")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")


def run_qt_dialog():
    # If Qt is available, show Qt dialog; otherwise fallback to Tkinter
    if HAVE_QT:
        app = QApplication.instance() or QApplication(sys.argv)
        cfg = load_config(DEFAULTS)
        dlg = SettingsDialog(cfg)
        dlg.exec()
        return 0
    else:
        # Fallback to Tkinter settings window
        import config_window as tk_settings  # type: ignore

        tk_settings.main()
        return 0


def main():
    sys.exit(run_qt_dialog())


if __name__ == "__main__":
    main()
