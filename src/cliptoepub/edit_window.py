#!/usr/bin/env python3
"""
Pre-conversion Edit Window for Clipboard to ePub
Provides a GUI for editing and previewing content before conversion
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
import sys
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import json
import webbrowser
import tempfile
import html

logger = logging.getLogger('EditWindow')


class PreConversionEditor:
    """Window for editing content before converting to ePub"""

    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None,
                 on_convert: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None):
        """
        Initialize the editor window

        Args:
            content: Initial content to edit
            metadata: Initial metadata
            on_convert: Callback when user clicks Convert (receives edited content and metadata)
            on_cancel: Callback when user cancels
        """
        self.content = content
        self.metadata = metadata or {}
        self.on_convert = on_convert
        self.on_cancel = on_cancel
        self.preview_file = None

        # Create main window
        self.window = tk.Tk()
        self.window.title("Edit Before Converting to ePub")
        self.window.geometry("900x700")

        # Set minimum size
        self.window.minsize(700, 500)

        # Configure grid weights for resizing
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)

        # Try to use macOS-friendly theme and set icon
        try:
            style = ttk.Style()
            try:
                style.theme_use('aqua')
            except tk.TclError:
                try:
                    style.theme_use('clam')
                except tk.TclError:
                    # Use default theme
                    pass
            icon_png = (Path(__file__).resolve().parent.parent / "resources" / "icon_64.png")
            if icon_png.exists():
                self.window.iconphoto(True, tk.PhotoImage(file=str(icon_png)))
        except (tk.TclError, OSError) as e:
            logger.debug(f"Could not set theme or icon: {e}")

        self.setup_ui()
        self.load_content()

        # Center window on screen
        self.center_window()

        # Bind keyboard shortcuts
        self.setup_shortcuts()

    def setup_ui(self):
        """Set up the user interface"""
        # Create main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title and metadata section
        self.setup_metadata_section(main_frame)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        # Content editor tab
        self.setup_editor_tab()

        # Preview tab
        self.setup_preview_tab()

        # Settings tab
        self.setup_settings_tab()

        # Buttons
        self.setup_buttons(main_frame)

    def setup_metadata_section(self, parent):
        """Set up metadata input fields"""
        metadata_frame = ttk.LabelFrame(parent, text="Metadata", padding="10")
        metadata_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        metadata_frame.grid_columnconfigure(1, weight=1)
        metadata_frame.grid_columnconfigure(3, weight=1)

        # Title
        ttk.Label(metadata_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.title_var = tk.StringVar(value=self.metadata.get('title', 'Untitled'))
        self.title_entry = ttk.Entry(metadata_frame, textvariable=self.title_var, width=40)
        self.title_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        # Author
        ttk.Label(metadata_frame, text="Author:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.author_var = tk.StringVar(value=self.metadata.get('author', 'Unknown Author'))
        self.author_entry = ttk.Entry(metadata_frame, textvariable=self.author_var, width=30)
        self.author_entry.grid(row=0, column=3, sticky=(tk.W, tk.E))

        # Language
        ttk.Label(metadata_frame, text="Language:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.language_var = tk.StringVar(value=self.metadata.get('language', 'en'))
        self.language_entry = ttk.Entry(metadata_frame, textvariable=self.language_var, width=10)
        self.language_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        # Style
        ttk.Label(metadata_frame, text="Style:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.style_var = tk.StringVar(value=self.metadata.get('style', 'default'))
        self.style_entry = ttk.Entry(metadata_frame, textvariable=self.style_var, width=20)
        self.style_entry.grid(row=1, column=3, sticky=(tk.W, tk.E))

    def setup_editor_tab(self):
        """Set up the content editor tab"""
        editor_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(editor_frame, text="Editor")

        # Editor text area
        self.editor = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD, height=20)
        self.editor.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        editor_frame.grid_rowconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        # Load initial content
        self.editor.insert("1.0", self.content)

    def setup_preview_tab(self):
        """Set up the preview tab"""
        preview_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(preview_frame, text="Preview")

        self.preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, height=20, state=tk.DISABLED)
        self.preview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        # Buttons for preview actions
        btn_frame = ttk.Frame(preview_frame)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        # Preview interpretation mode
        self.preview_mode_var = tk.StringVar(value=self._guess_initial_preview_mode())
        ttk.Label(btn_frame, text="Interpret as:").grid(row=0, column=0, padx=(0, 5))
        ttk.Radiobutton(
            btn_frame,
            text="Text",
            value="text",
            variable=self.preview_mode_var,
            command=self.refresh_preview,
        ).grid(row=0, column=1, padx=(0, 5))
        ttk.Radiobutton(
            btn_frame,
            text="Markdown",
            value="markdown",
            variable=self.preview_mode_var,
            command=self.refresh_preview,
        ).grid(row=0, column=2, padx=(0, 5))
        ttk.Radiobutton(
            btn_frame,
            text="HTML",
            value="html",
            variable=self.preview_mode_var,
            command=self.refresh_preview,
        ).grid(row=0, column=3, padx=(0, 15))

        ttk.Button(btn_frame, text="Refresh Preview", command=self.refresh_preview).grid(row=0, column=4, padx=(0, 10))
        ttk.Button(btn_frame, text="Open in Browser", command=self.open_preview_in_browser).grid(row=0, column=5)

    def setup_settings_tab(self):
        """Set up the settings tab"""
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="Settings")

        # Placeholder for additional settings if needed
        ttk.Label(settings_frame, text="No additional settings available.").grid(row=0, column=0, sticky=tk.W)

    def setup_buttons(self, parent):
        """Set up the bottom action buttons"""
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=3, column=0, sticky=(tk.E), pady=(10, 0))
        ttk.Button(btn_frame, text="Convert", command=self.on_convert_click).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel_click).grid(row=0, column=1)

    def load_content(self):
        """Load content into editor and preview"""
        self.refresh_preview()

    def refresh_preview(self):
        """Refresh the preview content"""
        # Always use the latest content from the editor
        try:
            edited_content = self.editor.get("1.0", tk.END).rstrip()
        except Exception:
            edited_content = self.content
        self.content = edited_content

        mode = self._get_preview_mode()
        preview_text = self._render_preview_text(edited_content, mode)

        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", preview_text)
        self.preview_text.config(state=tk.DISABLED)

    def open_preview_in_browser(self):
        """Open a temporary HTML file with the preview content in the default browser"""
        try:
            try:
                edited_content = self.editor.get("1.0", tk.END).rstrip()
            except Exception:
                edited_content = self.content
            self.content = edited_content
            mode = self._get_preview_mode()
            html_content = self._render_preview_html(edited_content, mode)
            with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                self.preview_file = f.name
            webbrowser.open(f"file://{self.preview_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open preview in browser: {e}")

    def center_window(self):
        """Center the window on the screen"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        self.window.bind('<Command-s>' if sys.platform == 'darwin' else '<Control-s>', lambda e: self.on_convert_click())
        self.window.bind('<Escape>', lambda e: self.on_cancel_click())

    def on_convert_click(self):
        """Handle Convert button click"""
        try:
            edited_content = self.editor.get("1.0", tk.END).strip()
            self.content = edited_content
            # Update metadata from UI
            self.metadata['title'] = self.title_var.get()
            self.metadata['author'] = self.author_var.get()
            self.metadata['language'] = self.language_var.get()
            self.metadata['style'] = self.style_var.get()
            if self.on_convert:
                self.on_convert(self.content, self.metadata)
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Could not process content: {e}")

    def on_cancel_click(self):
        """Handle Cancel button click"""
        if self.on_cancel:
            try:
                self.on_cancel()
            except Exception:
                pass
        self.window.destroy()

    def run(self):
        """Run the editor window loop"""
        self.window.mainloop()

    def _guess_initial_preview_mode(self) -> str:
        """Heuristic to choose an initial preview mode based on the content text."""
        text = (self.content or "").lstrip()
        lowered = text.lower()

        # Basic HTML heuristic
        if "<html" in lowered or "<body" in lowered or "<p" in lowered or "<div" in lowered or "</" in text:
            return "html"

        # Simple Markdown signals in the first lines
        lines = text.splitlines()
        head = lines[:20]
        for line in head:
            stripped = line.lstrip()
            if stripped.startswith(("# ", "## ", "### ", "- ", "* ", "1. ")):
                return "markdown"

        return "text"

    def _get_preview_mode(self) -> str:
        """Return the current preview mode: 'text', 'markdown' or 'html'."""
        try:
            mode = self.preview_mode_var.get()
        except Exception:
            mode = "text"
        if mode not in ("text", "markdown", "html"):
            return "text"
        return mode

    def _get_preview_css(self) -> str:
        """Return CSS for preview, preferring templates when available."""
        # Prefer CSS templates from packaged content_processor if available
        try:
            from .content_processor import CSSTemplates  # type: ignore

            try:
                style_name = (self.style_var.get() or "default").strip() or "default"
            except Exception:
                style_name = "default"

            templates = CSSTemplates()
            css = templates.get_template(style_name)
            if css:
                return css
        except Exception:
            # Fall back to a simple built-in CSS suitable for browser preview
            pass

        return """
        body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin: 1.5rem; line-height: 1.6; }
        pre { background: #f5f5f5; padding: 10px; }
        code { background: #f5f5f5; padding: 2px 4px; }
        h1, h2, h3, h4 { margin-top: 1.2em; }
        """

    def _render_preview_html(self, content: str, mode: str) -> str:
        """Build an HTML document for the current preview mode."""
        css = self._get_preview_css()

        body_inner = ""
        if mode == "markdown":
            try:
                import markdown2  # type: ignore

                body_inner = markdown2.markdown(content or "")
            except Exception:
                body_inner = f"<pre>{html.escape(content or '')}</pre>"
        elif mode == "html":
            # Optionally sanitize HTML if lxml_html_clean is available
            cleaned = content or ""
            try:
                from lxml_html_clean import clean_html  # type: ignore

                try:
                    cleaned = clean_html(cleaned)
                except Exception:
                    cleaned = content or ""
            except Exception:
                cleaned = content or ""
            body_inner = cleaned or ""
        else:
            body_inner = f"<pre>{html.escape(content or '')}</pre>"

        return f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8"/>
    <style>
{css}
    </style>
  </head>
  <body>
{body_inner}
  </body>
</html>
"""

    def _render_preview_text(self, content: str, mode: str) -> str:
        """Render preview text for the in-window widget."""
        if mode == "text":
            return content

        # For Markdown/HTML, render to HTML and then strip tags to get a readable text preview
        try:
            html_content = self._render_preview_html(content, mode)
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html_content, "html.parser")
            # Use newlines to preserve basic structure (headings, paragraphs)
            text = soup.get_text("\n")
            return text.strip()
        except Exception:
            return content
