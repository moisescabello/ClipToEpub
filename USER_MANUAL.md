# Clipboard to ePub - User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Getting Started](#getting-started)
5. [Features](#features)
6. [Usage Guide](#usage-guide)
7. [Keyboard Shortcuts](#keyboard-shortcuts)
8. [Configuration](#configuration)
9. [Supported Formats](#supported-formats)
10. [Troubleshooting](#troubleshooting)
11. [FAQs](#faqs)

---

## Introduction

**Clipboard to ePub** is a powerful application that instantly converts your clipboard content into professionally formatted ePub files with just a keyboard shortcut. On macOS it runs as a menubar app; on Windows it runs as a system tray application. Whether you're collecting research, saving articles, or organizing notes, this tool makes it effortless to create portable ebook files.

### Key Benefits
- **Instant Conversion**: Press Cmd+Shift+E to convert clipboard to ePub
- **Multiple Formats**: Supports text, Markdown, HTML, RTF, URLs, and images
- **Smart Processing**: Automatic format detection and intelligent conversion
- **Professional Output**: Creates valid, well-formatted ePub files
- **Menubar Integration**: Non-intrusive menubar app with quick access

---

## System Requirements

- **Operating System**: macOS 10.15+ or Windows 10/11
- **Processor**: Apple Silicon (M1/M2) or Intel/AMD
- **Memory**: 2GB RAM minimum, 4GB recommended
- **Storage**: 200MB available disk space
- **Python**: 3.9 or later (included in macOS app bundle)

---

## Installation

### Method 1: DMG Installer (Recommended)

1. Download `ClipboardToEpub-1.0.0.dmg`
2. Double-click to mount the DMG
3. Drag **Clipboard to ePub** to your Applications folder
4. Eject the DMG
5. Launch from Applications or Launchpad

### Method 2: Direct App Bundle

1. Download and unzip the app bundle
2. Move `Clipboard to ePub.app` to `/Applications`
3. Right-click and select "Open" on first launch
4. Grant necessary permissions when prompted

### Method 3: From Source (macOS)

```bash
# Clone repository
git clone https://github.com/clipboardtoepub/clipboard-to-epub.git
cd clipboard-to-epub

# Run setup script
./setup.sh

# Launch application
./run_menubar.sh
```

### Required Permissions (macOS)

On first launch, grant these permissions:
1. **Accessibility**: System Preferences → Security & Privacy → Privacy → Accessibility
2. **Input Monitoring**: For global hotkey support
3. **Files and Folders**: To save ePub files

---

## Getting Started

### Quick Start (macOS)

1. **Launch the App**
   - Find "Clipboard to ePub" in Applications
   - The 📋 icon appears in your menubar

2. **Copy Content**
   - Copy any text, article, or image to clipboard
   - Supports selecting text from any application

3. **Convert to ePub**
   - Press `Cmd+Shift+E`
   - A notification confirms successful conversion
   - Find your ePub in `~/Documents/ClipboardEpubs/`

### First-Time Setup (macOS)

1. Click the 📋 icon in menubar
2. Select "⚙️ Configuration"
3. Set your preferred:
   - Output directory
   - Default author name
   - Book language
   - CSS style template

---

## Features

### Core Features

#### 1. Instant Conversion
- Global hotkey (Cmd+Shift+E) works from any app
- Sub-second conversion for typical content
- Background processing for large files

#### 2. Smart Format Detection
- Automatically identifies content type
- Applies appropriate conversion method
- Preserves formatting and structure

#### 3. Multi-Clip Accumulator
- Accumulate multiple clips: `Cmd+Shift+A`
- Combine into single ePub: `Cmd+Shift+C`
- Perfect for research compilation

#### 4. Image Processing
- Embed images directly in ePub
- Automatic optimization for file size
- OCR support for text extraction

#### 5. Web Article Extraction
- Paste URLs to download full articles
- Clean extraction removing ads/navigation
- Preserves images and formatting

#### 6. Conversion History
- Track all conversions
- Quick access to recent files
- Search and filter capabilities

### Advanced Features

- **Chapter Division**: Automatically splits long content
- **Table of Contents**: Generated for multi-chapter books
- **Metadata Extraction**: Smart title and author detection
- **Custom Styling**: Three professional CSS templates
- **Edit Before Save**: Preview and edit window option
- **Cache System**: Instant re-conversion of recent content

---

## Usage Guide

### Basic Workflow

1. **Simple Text Conversion**
   ```
   Copy text → Cmd+Shift+E → ePub created
   ```

2. **Markdown Document**
   ```
   Copy .md content → Cmd+Shift+E → Formatted ePub
   ```

3. **Web Article**
   ```
   Copy article URL → Cmd+Shift+E → Article ePub
   ```

4. **Image with Text**
   ```
   Copy image → Cmd+Shift+E → ePub with embedded image
   ```

### Advanced Workflows

#### Research Compilation
1. Copy first source → `Cmd+Shift+A` (accumulate)
2. Copy second source → `Cmd+Shift+A` (accumulate)
3. Continue adding sources...
4. Press `Cmd+Shift+C` to combine all into one ePub

#### Book Creation from Multiple Chapters
1. Copy chapter 1 → `Cmd+Shift+A`
2. Copy chapter 2 → `Cmd+Shift+A`
3. Continue for all chapters
4. `Cmd+Shift+C` creates complete book with TOC

#### Batch URL Processing
1. Copy multiple URLs (one per line)
2. Press `Cmd+Shift+E`
3. Each URL becomes a chapter in the ePub

---

## Keyboard Shortcuts

### Global Hotkeys
| Shortcut | Action | Description |
|----------|--------|-------------|
| `Cmd+Shift+E` | Convert | Convert clipboard to ePub |
| `Cmd+Shift+A` | Accumulate | Add clipboard to accumulator |
| `Cmd+Shift+C` | Combine | Create ePub from accumulated clips |
| `ESC` | Stop | Stop the converter (when focused) |

On Windows, the default convert shortcut is `Ctrl+Shift+E`.

### Menubar Shortcuts
| Action | Description |
|--------|-------------|
| Click 📋 | Open menu |
| `⌘Q` | Quit application |

---

## Configuration

### Settings Window

Access via menubar → ⚙️ Configuration

#### General Settings
- **Output Directory**: Where ePub files are saved
- **Auto-open Files**: Open ePub after creation
- **Show Notifications**: Display success/error messages

#### Metadata Defaults
- **Author Name**: Default author for all books
- **Publisher**: Your publisher name
- **Language**: Book language code (en, es, fr, etc.)

#### Processing Options
- **CSS Style**: Choose from default, minimal, or modern
- **Chapter Length**: Words per chapter (0 = no splitting)
- **Image Quality**: JPEG compression level
- **OCR Language**: For text extraction from images

#### Advanced
- **Cache Duration**: How long to cache conversions
- **Worker Threads**: For parallel processing
- **Debug Mode**: Enable detailed logging

### Configuration File

- macOS: `~/Library/Preferences/clipboard-to-epub.json`
- Windows: `%APPDATA%\ClipboardToEpub\config.json`

Example configuration:
```json
{
  "output_dir": "~/Documents/ClipboardEpubs",
  "author": "John Doe",
  "language": "en",
  "style_template": "modern",
  "auto_open": true,
  "show_notifications": true,
  "chapter_words": 5000,
  "image_quality": 85,
  "cache_hours": 24,
  "worker_threads": 3
}
```

---

## Windows Usage

### Launching the Tray App

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
run_tray_windows.bat
# or: python src\tray_app_windows.py
```

- The app icon appears in the Windows system tray (notification area).
- Right-click the icon to access “Convert Now”, “Recent Conversions”, toggles, Settings, and Quit.
- Default hotkey: `Ctrl+Shift+E`.

### Output and Recent Files
- ePub files are saved by default to `Documents\ClipboardEpubs`.
- “Recent Conversions” shows the last 10 `.epub` files; select to open.

### Packaging on Windows

One-folder (recommended to reduce AV false positives):

```
pyinstaller --noconfirm "build scripts\pyinstaller_tray_windows.spec"
```

### Uninstall (Windows)
- Delete the installed folder (if packaged), and remove `%APPDATA%\ClipboardToEpub\` to reset configuration/history.

---

## Supported Formats

### Input Formats

| Format | Extension | Features |
|--------|-----------|----------|
| Plain Text | .txt | Basic paragraph detection |
| Markdown | .md | Full syntax support |
| HTML | .html | Preserves structure |
| RTF | .rtf | Maintains formatting |
| URL | http(s) | Article extraction |
| Images | .png/.jpg | Embed + OCR |
| Mixed | - | Smart detection |

### Markdown Support
- Headers (h1-h6)
- Bold, italic, strikethrough
- Links and images
- Code blocks and inline code
- Lists (ordered/unordered)
- Tables
- Blockquotes

### URL Processing
- News articles
- Blog posts
- Wiki pages
- Documentation
- Medium articles
- Scientific papers

---

## Troubleshooting

### Common Issues

#### App Doesn't Launch
1. Check macOS version (10.15+)
2. Right-click → Open on first launch
3. Check Security & Privacy settings

#### Hotkeys Not Working
1. Grant Accessibility permissions
2. Restart the application
3. Check for conflicts with other apps

#### No ePub Created
1. Ensure clipboard has content
2. Check output directory permissions
3. Look for error notifications

#### Images Not Embedded
1. Check image format (PNG/JPEG)
2. Verify file size (<10MB)
3. Enable image processing in settings

### Error Messages

| Error | Solution |
|-------|----------|
| "Empty clipboard" | Copy content before converting |
| "Permission denied" | Grant required permissions |
| "Invalid URL" | Check URL format and connectivity |
| "Conversion failed" | Check logs in Console.app |

### Log Files

Debug logs location:
```
~/Library/Logs/ClipboardToEpub/
```

To enable verbose logging:
1. Open Configuration
2. Enable "Debug Mode"
3. Restart application

---

## FAQs

**Q: Can I customize the keyboard shortcuts?**
A: Currently, shortcuts are fixed. Custom shortcuts will be added in v2.0.

**Q: What's the maximum file size?**
A: No hard limit, but files over 50MB may process slowly.

**Q: Can I convert multiple files at once?**
A: Use the accumulator feature (Cmd+Shift+A) to combine multiple clips.

**Q: Does it work offline?**
A: Yes, except for URL downloading which requires internet.

**Q: Can I edit the ePub after creation?**
A: Yes, use any ePub editor like Calibre or Sigil.

**Q: Is my clipboard content stored?**
A: Only in the output ePub files and optional cache. Nothing is uploaded.

**Q: How do I uninstall?**
A: On macOS, drag app to Trash and delete `~/Library/Preferences/clipboard-to-epub.json`. On Windows, remove the app folder and delete `%APPDATA%\ClipboardToEpub\`.

**Q: Can I use custom CSS?**
A: Place custom .css files in the templates folder.

**Q: Does it support other ebook formats?**
A: Currently only ePub. PDF and MOBI planned for v2.0.

**Q: How do I report bugs?**
A: Visit https://github.com/clipboardtoepub/issues

---

## Support

- **Documentation**: https://clipboardtoepub.readthedocs.io
- **GitHub Issues**: https://github.com/clipboardtoepub/issues
- **Email Support**: support@clipboardtoepub.app
- **Twitter**: @clipboardtoepub

---

## License

Clipboard to ePub is released under the MIT License.

---

## Credits

Created with ❤️ by the Clipboard to ePub Team

Special thanks to all contributors and beta testers.
