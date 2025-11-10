# 📋 ClipToEpub

Convert clipboard content to ePub with a single global hotkey. Runs as a macOS menu bar app and a Windows system tray app.

## 📋 Prerequisites

- macOS 10.15 or later
- Python 3.9 or later
- pip (Python package manager)

## 🔧 Installation

### Option 1: Automatic Installation (Recommended)

```bash
# Clone or download this repository, then run:
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Installation

1. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Grant necessary permissions (macOS):**
   - Go to System Settings → Privacy & Security → Accessibility
   - Add Terminal (or your Python interpreter) to the allowed apps

## 🎯 Usage

### macOS (Menu Bar)

```bash
source venv/bin/activate
./run_menubar.sh
# or
python src/menubar_app.py
```

- Default hotkey: Cmd + Shift + E
- Output: `~/Documents/ClipToEpubs/`
- Quick toggles in the menu: Auto-open, Notifications, Recent Conversions, Settings

### Windows (Tray App)

```bat
run_tray_windows.bat
:: or
python src\tray_app_windows.py
```

- Default hotkey: Ctrl + Shift + E
- Output: `C:\Users\<you>\Documents\ClipToEpubs\`
- Click the tray icon for menu: Convert Now, Recent, Settings, toggles

## ⚙️ Configuration & Paths

- macOS config: `~/Library/Preferences/cliptoepub.json`
- Windows config: `%APPDATA%\ClipToEpub\config.json` (auto-migration from legacy paths)
- History (if enabled): `~/.cliptoepub/history.json` (macOS) or `%APPDATA%\ClipToEpub\history.json` (Windows)
- Output directory (default): `~/Documents/ClipToEpubs/` or `C:\Users\<you>\Documents\ClipToEpubs\`

Note: Hotkey is fixed by platform (Cmd+Shift+E on macOS, Ctrl+Shift+E on Windows). Future versions may add a UI to customize it.

## 📁 Project Structure

```
ClipToEpub/
├── src/
│   ├── menubar_app.py           # macOS menu bar app (Phase 3)
│   ├── tray_app_windows.py      # Windows tray app (PySide6)
│   ├── clipboard_to_epub*.py    # Phase 1-4 converters
│   ├── config_window_qt.py      # Settings (Qt, preferred)
│   ├── config_window.py         # Settings (Tkinter, fallback)
│   ├── edit_window.py           # Editor UI (Tkinter)
│   ├── history_manager.py       # Conversion history
│   ├── image_handler.py         # Image processing (Phase 4)
│   ├── update_checker.py        # Update management
│   ├── paths.py                 # Cross-platform config/history paths
│   └── imp_patch.py             # Compatibility patch
├── templates/                   # CSS templates (default, minimal, modern)
├── resources/                   # Icons
├── build scripts/               # PyInstaller specs (Windows)
│   ├── file_version.txt
│   ├── pyinstaller_onefile.spec
│   ├── pyinstaller_onefolder.spec
│   └── pyinstaller_tray_windows.spec
├── build_app_fixed.sh           # macOS py2app build
├── build_complete.sh            # macOS full build
├── build_dmg.sh                 # macOS DMG creation
├── create_app_bundle.sh         # macOS lightweight bundle
├── run_menubar.sh               # macOS runner
├── run_tray_windows.bat         # Windows runner
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

## ⌨️ Keyboard Shortcuts

- macOS: Cmd + Shift + E
- Windows: Ctrl + Shift + E

## 🔍 Features

### Current
- ✅ Global hotkey capture (platform-specific)
- ✅ Smart content detection (Markdown, HTML, RTF, URLs)
- ✅ Chapter splitting and Table of Contents
- ✅ CSS styling (default, minimal, modern)
- ✅ Recent conversions menu and notifications
- ✅ Settings window (Qt preferred; Tk fallback)
- ✅ Windows tray app (QSystemTrayIcon)

### Optional / Advanced
- 🔄 Phase 4 modules for images/OCR and URL enhancements (`src/clipboard_to_epub_v4.py`)

## 🐛 Troubleshooting

### "Permission denied" error
- Ensure Terminal has accessibility permissions in System Preferences

### Keyboard shortcut not working
- Make sure no other app is using Cmd+Shift+E
- Try restarting the application
- Check that the app has focus

### Empty ePub files
- Ensure clipboard has text content
- Try copying text again before pressing the hotkey

### Module not found errors
- Make sure virtual environment is activated
- Reinstall requirements: `pip install -r requirements.txt`
- If you see "lxml.html.clean is now a separate project": `pip install lxml_html_clean`

### py2app launch error (macOS)
- "ModuleNotFoundError: No module named 'imp'" → prefer the lightweight bundle (`./create_app_bundle.sh`).

### Tray icon not visible (Windows)
- Check the hidden icons chevron and ensure the app is running.

## 📊 System Requirements

- **OS:** macOS 10.15+
- **Python:** 3.9+
- **RAM:** 50MB
- **Disk Space:** 10MB + space for ePub files

## 🤝 Contributing

This project is in active development.

## 📝 License

MIT License - Feel free to use and modify as needed.

## 🆘 Support

For issues or questions:
- Check the troubleshooting section above
- Review the development plan in `plan.md`
- Create an issue in the repository

---

**Current Version:** 1.0.0 (Phase 3: Menubar + Windows Tray)
**Last Updated:** November 2025
