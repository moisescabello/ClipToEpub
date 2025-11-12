#!/usr/bin/env python3
"""
Unified Clipboard to ePub converter

Consolidates previous phased converters into a single module with optional
advanced features (images, OCR, URL fetching, accumulator, caching, history).
"""

from __future__ import annotations

import asyncio
import re
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pyperclip
from ebooklib import epub
from PIL import Image
from pynput import keyboard

import os
import sys

# Ensure repository root is on sys.path so top-level modules resolve (content_processor)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Local imports
try:
    # Prefer package import when run from app scripts
    from src import paths as paths  # type: ignore
except Exception:
    # Fallback when executed with CWD on src/
    import paths  # type: ignore
from content_processor import process_clipboard_content
try:
    from src.history_manager import ClipboardAccumulator, ConversionCache, ConversionHistory  # type: ignore
except Exception:
    from history_manager import ClipboardAccumulator, ConversionCache, ConversionHistory  # type: ignore
try:
    from src.image_handler import ImageHandler  # type: ignore
except Exception:
    from image_handler import ImageHandler  # type: ignore
try:
    from src.edit_window import PreConversionEditor  # type: ignore
except Exception:
    from edit_window import PreConversionEditor  # type: ignore


# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ClipboardToEpub")


def _platform_hotkeys():
    """Return default hotkey sets for the current platform.

    Returns a tuple: (convert, accumulate, combine)
    """
    try:
        if sys.platform.startswith("win") or sys.platform.startswith("linux"):
            convert = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char("e")}
            accumulate = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char("a")}
            combine = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char("c")}
        else:
            convert = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char("e")}
            accumulate = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char("a")}
            combine = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char("c")}
        return convert, accumulate, combine
    except Exception as e:
        # Conservative fallback if certain keys are unavailable
        logger.warning(f"Could not set platform hotkeys: {e}")
        return (
            {keyboard.Key.shift, keyboard.KeyCode.from_char("e")},
            {keyboard.Key.shift, keyboard.KeyCode.from_char("a")},
            {keyboard.Key.shift, keyboard.KeyCode.from_char("c")},
        )


# Defaults
DEFAULT_OUTPUT_DIR = paths.get_default_output_dir()
DEFAULT_CONVERT_HOTKEY, DEFAULT_ACCUMULATE_HOTKEY, DEFAULT_COMBINE_HOTKEY = _platform_hotkeys()


class ClipboardToEpubConverter:
    """Unified converter with optional advanced features and callbacks."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        default_author: str = "Unknown Author",
        default_language: str = "en",
        default_style: str = "default",
        chapter_words: int = 5000,
        enable_ocr: bool = False,
        enable_cache: bool = True,
        enable_history: bool = True,
        enable_edit_window: bool = False,
        hotkey_combo: Optional[set] = None,
        max_async_workers: int = 3,
        # YouTube subtitles + LLM
        youtube_langs: Optional[List[str]] = None,
        youtube_prefer_native: bool = True,
        yt_dlp_binary: str = "yt-dlp",
        # LLM config (optional; used when processing YouTube subs)
        llm_provider: str = "openrouter",
        anthropic_api_key: str = "",
        openrouter_api_key: str = "",
        anthropic_model: str = "anthropic/claude-sonnet-4.5",
        anthropic_prompt: str = "",
        anthropic_max_tokens: int = 2048,
        anthropic_temperature: float = 0.2,
        anthropic_timeout_seconds: int = 60,
        anthropic_retry_count: int = 10,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.default_author = default_author
        self.default_language = default_language
        self.default_style = default_style
        self.chapter_words = chapter_words
        self.enable_ocr = enable_ocr
        self.enable_cache = enable_cache
        self.enable_history = enable_history
        self.enable_edit_window = enable_edit_window
        self.max_async_workers = max_async_workers

        # Hotkeys
        self.convert_hotkey = hotkey_combo or DEFAULT_CONVERT_HOTKEY
        self.accumulate_hotkey = DEFAULT_ACCUMULATE_HOTKEY
        self.combine_hotkey = DEFAULT_COMBINE_HOTKEY

        # Components
        self.image_handler = ImageHandler(enable_ocr=enable_ocr, optimize_images=True)
        self.history = ConversionHistory() if enable_history else None
        self.accumulator = ClipboardAccumulator(max_clips=50)
        self.cache = ConversionCache() if enable_cache else None

        # YouTube + LLM settings
        self.youtube_langs: List[str] = [
            *(youtube_langs or ["en", "es", "pt"])
        ]
        # sanitize and cap to 3 unique entries
        langs_norm = []
        for c in self.youtube_langs:
            cc = str(c or "").strip().lower()
            if cc and cc not in langs_norm:
                langs_norm.append(cc)
            if len(langs_norm) >= 3:
                break
        self.youtube_langs = langs_norm or ["en", "es", "pt"]
        self.youtube_prefer_native = bool(youtube_prefer_native)
        self.yt_dlp_binary = yt_dlp_binary or "yt-dlp"

        # LLM config for YouTube flow
        self.llm_provider = (llm_provider or "openrouter").strip().lower()
        self.anthropic_api_key = anthropic_api_key or ""
        self.openrouter_api_key = openrouter_api_key or ""
        self.anthropic_model = anthropic_model or "anthropic/claude-sonnet-4.5"
        self.anthropic_prompt = anthropic_prompt or ""
        self.anthropic_max_tokens = int(anthropic_max_tokens or 2048)
        self.anthropic_temperature = float(anthropic_temperature or 0.2)
        self.anthropic_timeout_seconds = int(anthropic_timeout_seconds or 60)
        self.anthropic_retry_count = int(anthropic_retry_count or 10)

        # Listener state
        self.current_keys: set = set()
        self.listener: Optional[keyboard.Listener] = None
        self.listening: bool = False

        # Callbacks
        self.conversion_callback = None
        self.error_callback = None

        # Async executor
        self.executor = None

        self._ensure_output_dir()
        self._setup_async()

    # --------- Setup ---------
    def _ensure_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")

    def _setup_async(self) -> None:
        try:
            from concurrent.futures import ThreadPoolExecutor

            self.executor = ThreadPoolExecutor(max_workers=self.max_async_workers)
            logger.info(f"Async executor initialized with {self.max_async_workers} workers")
        except Exception as e:
            logger.error(f"Failed to setup async executor: {e}")

    # --------- Public API ---------
    def convert_clipboard_content(self, use_accumulator: bool = False) -> Optional[str]:
        """Synchronous wrapper around the async conversion method."""
        try:
            # If an event loop is already running, run the async conversion in a worker thread
            try:
                asyncio.get_running_loop()
                loop_running = True
            except RuntimeError:
                loop_running = False

            if loop_running:
                result: Dict[str, Optional[str]] = {"path": None}
                error: Dict[str, Optional[BaseException]] = {"e": None}

                def _runner():
                    try:
                        result["path"] = asyncio.run(
                            self.convert_clipboard_content_async(use_accumulator=use_accumulator)
                        )
                    except BaseException as e:  # propagate fatal exceptions
                        error["e"] = e

                t = threading.Thread(target=_runner, daemon=True)
                t.start()
                t.join(timeout=30)
                if t.is_alive():
                    logger.error("Conversion timed out after 30 seconds")
                    return None
                if error["e"] is not None:
                    raise error["e"]
                return result["path"]

            return asyncio.run(self.convert_clipboard_content_async(use_accumulator=use_accumulator))
        except Exception as e:
            logger.error(f"Error in sync conversion: {e}")
            return None

    def convert_text_to_epub(self, text: str, suggested_title: Optional[str] = None, tags: Optional[List[str]] = None) -> Optional[str]:
        """Convert provided text directly to ePub, bypassing clipboard detection."""
        try:
            try:
                asyncio.get_running_loop()
                loop_running = True
            except RuntimeError:
                loop_running = False

            if loop_running:
                result: Dict[str, Optional[str]] = {"path": None}
                error: Dict[str, Optional[BaseException]] = {"e": None}

                def _runner():
                    try:
                        result["path"] = asyncio.run(
                            self.convert_text_to_epub_async(text, suggested_title=suggested_title, tags=tags)
                        )
                    except BaseException as e:  # propagate fatal exceptions
                        error["e"] = e

                t = threading.Thread(target=_runner, daemon=True)
                t.start()
                t.join(timeout=30)
                if t.is_alive():
                    logger.error("Conversion timed out after 30 seconds")
                    return None
                if error["e"] is not None:
                    raise error["e"]
                return result["path"]

            return asyncio.run(self.convert_text_to_epub_async(text, suggested_title=suggested_title, tags=tags))
        except Exception as e:
            logger.error(f"Error converting provided text: {e}")
            return None

    async def convert_text_to_epub_async(self, text: str, suggested_title: Optional[str] = None, tags: Optional[List[str]] = None) -> Optional[str]:
        try:
            if not text or not text.strip():
                logger.warning("No text provided for direct conversion")
                return None

            # Use the same processing pipeline but bypass clipboard detection
            loop = asyncio.get_running_loop()
            options = {"words_per_chapter": self.chapter_words, "css_template": self.default_style}
            processed = await loop.run_in_executor(self.executor, process_clipboard_content, text, options)

            # Force title if suggested
            metadata = {"title": suggested_title} if suggested_title else {}
            if tags:
                metadata["tags"] = list(tags)

            path = await self._create_epub_async(processed, metadata)

            if self.history and path:
                try:
                    hist_meta = {
                        "title": processed.get("metadata", {}).get("title", suggested_title or "Untitled"),
                        "format": processed.get("format", "unknown"),
                        "chapters": len(processed.get("chapters", [])),
                        "size": Path(path).stat().st_size,
                        "author": self.default_author,
                        "tags": list(tags) if tags else [],
                    }
                    self.history.add_entry(path, hist_meta)
                except Exception:
                    pass

            return path
        except Exception as e:
            logger.error(f"Error in direct text conversion: {e}", exc_info=True)
            return None

    def start_listening(self) -> None:
        if self.listening:
            return

        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()
        self.listening = True

        def _label(combo: set) -> str:
            def fmt(k):
                if isinstance(k, keyboard.KeyCode):
                    return k.char.upper() if k.char else str(k)
                return str(k).split(".")[-1].upper()

            return "+".join(sorted(fmt(k) for k in combo))

        logger.info("Started listening for hotkeys")
        logger.info(f"  Convert: {_label(self.convert_hotkey)}")
        logger.info(f"  Accumulate: {_label(self.accumulate_hotkey)}")
        logger.info(f"  Combine: {_label(self.combine_hotkey)}")
        logger.info("  Stop: ESC")

    def stop_listening(self) -> None:
        if self.listening and self.listener:
            self.listener.stop()
            self.listening = False
            logger.info("Stopped listening for hotkeys")

    def accumulate_current_clip(self) -> None:
        try:
            content = pyperclip.paste()
            if content and content.strip():
                clip = self.accumulator.add_clip(content)
                logger.info(f"Added clip to accumulator: {clip['id']}")
                if self.conversion_callback:
                    self.conversion_callback(f"accumulator:{clip['id']}")
            else:
                logger.warning("No content to accumulate")
        except Exception as e:
            logger.error(f"Error accumulating clip: {e}")

    def combine_accumulated_clips(self) -> None:
        path = self.convert_clipboard_content(use_accumulator=True)
        if path:
            self.accumulator.clear()
            if self.conversion_callback:
                self.conversion_callback(path)

    def get_recent_conversions(self, limit: int = 10) -> List[Dict[str, Any]]:
        if self.history:
            return self.history.get_recent(limit)
        return []

    # --------- Internals / Async ---------
    async def convert_clipboard_content_async(
        self, clipboard_content: Optional[str] = None, use_accumulator: bool = False
    ) -> Optional[str]:
        try:
            # Source content and metadata
            # Priority: Images → URLs/Markdown/HTML/RTF/Plain (via processor)
            if not use_accumulator and clipboard_content is None:
                # Give priority to images currently in the clipboard
                try:
                    maybe_image = self.image_handler.detect_image_in_clipboard()
                except Exception:
                    maybe_image = None
                if maybe_image is not None:
                    logger.info("Image detected in clipboard (priority path)")
                    return await self._convert_image_to_epub_async(maybe_image)
            if use_accumulator:
                content = self.accumulator.combine_clips()
                metadata = self.accumulator.get_combined_metadata()
                if not content:
                    logger.warning("No accumulated clips to convert")
                    return None
            else:
                content = clipboard_content or await self._get_clipboard_content_async()
                metadata = {}

            if not content or not content.strip():
                # Fallback: check for image if no textual content
                try:
                    image = self.image_handler.detect_image_in_clipboard()
                except Exception:
                    image = None
                if image is not None:
                    logger.info("Image detected in clipboard (fallback path)")
                    return await self._convert_image_to_epub_async(image)
                logger.warning("No content to convert")
                return None

            # Optional edit window first so user changes affect processing and caching
            if self.enable_edit_window and not use_accumulator:
                edited_content, edited_meta = await self._show_edit_window_async(content, metadata)
                if edited_content:
                    content = edited_content
                    metadata.update(edited_meta)
                else:
                    logger.info("User cancelled conversion")
                    return None

            # Build processing options possibly overridden by metadata (from accumulator or editor)
            words_per_chapter = self.chapter_words
            if "chapter_words" in metadata:
                try:
                    words_per_chapter = int(metadata.get("chapter_words"))  # type: ignore[arg-type]
                except Exception:
                    words_per_chapter = self.chapter_words
            css_template = str(metadata.get("style", self.default_style))
            options = {"words_per_chapter": words_per_chapter, "css_template": css_template}

            # Cache check (after potential edits so we don't skip user's changes)
            if self.cache:
                cached = self.cache.get(content, options)
                if cached:
                    logger.info("Using cached conversion result")
                    return await self._create_epub_from_cached_async(cached)

            # Special case: If content is a bare YouTube URL, fetch subtitles and route via LLM
            try:
                if not use_accumulator and isinstance(content, str) and self._looks_like_youtube_url(content.strip()):
                    logger.info("YouTube URL detected; attempting subtitles + LLM pipeline")
                    path = await self._handle_youtube_url_async(content.strip())
                    if path:
                        return path
            except Exception as e:
                logger.warning(f"YouTube path failed; falling back to generic processing: {e}")

            # Process content (thread pool)
            loop = asyncio.get_running_loop()
            processed = await loop.run_in_executor(self.executor, process_clipboard_content, content, options)

            # Create ePub
            path = await self._create_epub_async(processed, metadata)

            # Cache store
            if self.cache and path:
                self.cache.put(content, options, processed)

            # History
            if self.history and path:
                hist_meta = {
                    "title": processed.get("metadata", {}).get("title", "Untitled"),
                    "format": processed.get("format", "unknown"),
                    "chapters": len(processed.get("chapters", [])),
                    "size": Path(path).stat().st_size,
                    "author": self.default_author,
                }
                self.history.add_entry(path, hist_meta)

            return path
        except Exception as e:
            logger.error(f"Error in async conversion: {e}", exc_info=True)
            if self.error_callback:
                self.error_callback(str(e))
            return None

    async def _get_clipboard_content_async(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, pyperclip.paste)

    # --------- YouTube subtitles + LLM helpers ---------
    @staticmethod
    def _looks_like_youtube_url(text: str) -> bool:
        try:
            from urllib.parse import urlparse, parse_qs
            u = urlparse(text.strip())
            if u.scheme not in {"http", "https"}:
                return False
            host = (u.netloc or "").lower()
            if any(h in host for h in ["youtube.com", "youtu.be"]):
                # quick sanity: if youtube.com check for /watch or shorts/live; youtu.be path holds id
                return True
            return False
        except Exception:
            return False

    async def _handle_youtube_url_async(self, url: str) -> Optional[str]:
        # Download subtitles with language + native/auto preference
        loop = asyncio.get_running_loop()
        try:
            transcript_text = await loop.run_in_executor(self.executor, self._download_youtube_subtitles_blocking, url)
        except Exception as e:
            logger.warning(f"yt-dlp invocation error: {e}")
            transcript_text = None

        if not transcript_text or not transcript_text.strip():
            logger.info("No subtitles retrieved for YouTube URL")
            return None

        # If LLM prompt not configured, fall back to direct conversion of transcript
        if not (self.anthropic_prompt and (self.anthropic_api_key or self.openrouter_api_key)):
            logger.info("LLM not configured; converting raw subtitles")
            return await self.convert_text_to_epub_async(transcript_text, suggested_title="YouTube Transcript", tags=["youtube", "subtitles"])  # type: ignore[arg-type]

        # Process via LLM
        try:
            md = await loop.run_in_executor(
                self.executor,
                self._llm_process_blocking,
                transcript_text,
            )
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            md = None

        if not md or not md.strip():
            logger.warning("Empty LLM result; converting transcript directly")
            return await self.convert_text_to_epub_async(transcript_text, suggested_title="YouTube Transcript", tags=["youtube", "subtitles"])  # type: ignore[arg-type]

        # Title from first line
        try:
            try:
                from src.llm_anthropic import sanitize_first_line  # type: ignore
            except Exception:
                from llm_anthropic import sanitize_first_line  # type: ignore
            suggested_title = sanitize_first_line(md)
        except Exception:
            suggested_title = "LLM Result"

        return await self.convert_text_to_epub_async(md, suggested_title=suggested_title, tags=["anthropic", "youtube"])  # type: ignore[arg-type]

    def _download_youtube_subtitles_blocking(self, url: str) -> Optional[str]:
        import subprocess
        import tempfile
        import time
        from pathlib import Path as _Path

        tmpdir = tempfile.mkdtemp(prefix="cte_yt_", dir=None)
        base = _Path(tmpdir)
        # capture baseline files to identify new ones after yt-dlp run
        before = {p.name for p in base.glob("*")}

        def run_cmd(args: List[str]) -> bool:
            try:
                proc = subprocess.run(args, cwd=str(base), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if proc.returncode == 0:
                    return True
                # Some failures still produce files; continue
                return False
            except FileNotFoundError:
                raise RuntimeError("yt-dlp not found. Install it with 'pip install yt-dlp' or via Homebrew.")
            except Exception as e:
                logger.debug(f"yt-dlp run error: {e}")
                return False

        # Helper: locate a newly created subtitle file, prefer vtt then srt
        def find_new_sub(lang_code: str) -> Optional[_Path]:
            new_files = [p for p in base.glob("*") if p.name not in before]
            # Prefer files that include language code in name
            lang_code_l = f".{lang_code.lower()}."
            candidates = [p for p in new_files if p.suffix.lower() in (".vtt", ".srt")]
            # Try to prioritize ones that contain the lang code
            preferred = [p for p in candidates if lang_code_l in p.name.lower()]
            pool = preferred or candidates
            if not pool:
                return None
            # choose the most recent
            pool.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return pool[0]

        # Iterate languages and native/auto preference
        subs_text: Optional[str] = None
        # yt-dlp args base
        common = [
            self.yt_dlp_binary,
            "--skip-download",
            "--no-playlist",
            "--sub-format",
            "vtt,srt",
        ]

        for lang in self.youtube_langs:
            tried_any = False
            if self.youtube_prefer_native:
                # Native first
                args = [*common, "--write-subs", "--sub-langs", lang, url]
                tried_any = True if run_cmd(args) else tried_any
                sub_path = find_new_sub(lang)
                if sub_path and sub_path.exists():
                    subs_text = self._parse_subtitle_file(sub_path)
                    if subs_text and subs_text.strip():
                        break
                # Auto next
                args = [*common, "--write-auto-subs", "--sub-langs", lang, url]
                tried_any = True if run_cmd(args) else tried_any
                sub_path = find_new_sub(lang)
                if sub_path and sub_path.exists():
                    subs_text = self._parse_subtitle_file(sub_path)
                    if subs_text and subs_text.strip():
                        break
            else:
                # Auto first
                args = [*common, "--write-auto-subs", "--sub-langs", lang, url]
                tried_any = True if run_cmd(args) else tried_any
                sub_path = find_new_sub(lang)
                if sub_path and sub_path.exists():
                    subs_text = self._parse_subtitle_file(sub_path)
                    if subs_text and subs_text.strip():
                        break
                # Native next
                args = [*common, "--write-subs", "--sub-langs", lang, url]
                tried_any = True if run_cmd(args) else tried_any
                sub_path = find_new_sub(lang)
                if sub_path and sub_path.exists():
                    subs_text = self._parse_subtitle_file(sub_path)
                    if subs_text and subs_text.strip():
                        break

        # Cleanup temp dir; keep errors silent
        try:
            import shutil as _shutil
            _shutil.rmtree(base, ignore_errors=True)
        except Exception:
            pass

        return subs_text

    def _parse_subtitle_file(self, path: "Path") -> str:
        try:
            data = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                data = Path(path).read_text(encoding="latin-1", errors="ignore")
            except Exception:
                return ""

        # Detect format by extension or header
        name_lower = str(path).lower()
        if name_lower.endswith(".vtt") or data.lstrip().upper().startswith("WEBVTT"):
            return self._vtt_to_text(data)
        return self._srt_to_text(data)

    @staticmethod
    def _vtt_to_text(vtt: str) -> str:
        lines = []
        for raw in (vtt or "").splitlines():
            s = raw.strip("\ufeff\n\r ")
            if not s:
                continue
            if s.upper().startswith("WEBVTT"):
                continue
            # Skip timestamp lines like 00:00:05.000 --> 00:00:07.000
            if "-->" in s and any(ch.isdigit() for ch in s):
                continue
            # Drop metadata/style markers
            if s.startswith("NOTE") or s.startswith("STYLE") or s.startswith("REGION"):
                continue
            lines.append(s)
        # Merge and de-duplicate consecutive caption lines
        text = "\n".join(lines)
        # Remove common annotations
        text = re.sub(r"\[(?:Music|Applause|Laughter|Silence)\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _srt_to_text(srt: str) -> str:
        lines = []
        for raw in (srt or "").splitlines():
            s = raw.strip()
            if not s:
                continue
            # Skip index numbers
            if s.isdigit():
                continue
            # Skip timestamp lines like 00:00:05,000 --> 00:00:07,000
            if "-->" in s and any(ch.isdigit() for ch in s):
                continue
            lines.append(s)
        text = " ".join(lines)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _llm_process_blocking(self, text: str) -> str:
        # Route based on provider + available key
        provider = (self.llm_provider or "anthropic").strip().lower()
        try:
            from src.llm_anthropic import process_text  # type: ignore
        except Exception:
            from llm_anthropic import process_text  # type: ignore

        if provider == "openrouter":
            api_key = (self.openrouter_api_key or "").strip() or os.environ.get("OPENROUTER_API_KEY", "")
            model = self.anthropic_model or "anthropic/claude-sonnet-4.5"
        else:
            api_key = (self.anthropic_api_key or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")
            # Accept both Anthropic id and OpenRouter id; process_text handles mapping
            model = self.anthropic_model or "claude-4.5-sonnet"

        return process_text(
            str(text or ""),
            api_key=str(api_key or ""),
            model=str(model or "claude-4.5-sonnet"),
            system_prompt=str(self.anthropic_prompt or ""),
            max_tokens=int(self.anthropic_max_tokens or 2048),
            temperature=float(self.anthropic_temperature or 0.2),
            timeout_s=int(self.anthropic_timeout_seconds or 60),
            retries=int(self.anthropic_retry_count or 10),
        )

    async def _convert_image_to_epub_async(self, image: Image.Image) -> Optional[str]:
        try:
            loop = asyncio.get_running_loop()
            image_data = await loop.run_in_executor(
                self.executor, self.image_handler.process_image_for_epub, image, None, self.enable_ocr
            )

            chapter = self.image_handler.create_image_chapter(image_data)
            processed = {
                "chapters": [chapter],
                "metadata": {"title": image_data["title"], "type": "image"},
                "format": "image",
                "css": self.image_handler.get_image_css(),
            }

            path = await self._create_epub_async(processed, {})

            if self.history and path:
                tags = ["image"]
                if image_data.get("has_text"):
                    tags.append("ocr")
                hist_meta = {
                    "title": image_data["title"],
                    "format": "image",
                    "chapters": 1,
                    "size": Path(path).stat().st_size,
                    "author": self.default_author,
                    "tags": tags,
                }
                self.history.add_entry(path, hist_meta)

            return path
        except Exception as e:
            logger.error(f"Error converting image: {e}", exc_info=True)
            return None

    async def _show_edit_window_async(self, content: str, metadata: Dict[str, Any]):
        result = {"content": None, "metadata": None}
        event = threading.Event()

        def on_convert(edited_content, edited_metadata):
            result["content"] = edited_content
            result["metadata"] = edited_metadata
            event.set()

        def on_cancel():
            event.set()

        def show_window():
            editor = PreConversionEditor(content=content, metadata=metadata, on_convert=on_convert, on_cancel=on_cancel)
            editor.run()

        t = threading.Thread(target=show_window)
        t.start()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, event.wait)
        return result["content"], result["metadata"] or {}

    async def _create_epub_from_cached_async(self, cached: Dict[str, Any]) -> Optional[str]:
        try:
            chapters = cached.get("chapters", [])
            proc_metadata = cached.get("metadata", {})
            css_style = cached.get("css", "")
            format_type = cached.get("format", "plain")
            toc_html = cached.get("toc_html")

            if not chapters:
                logger.warning("Cached data has no chapters")
                return None

            book = epub.EpubBook()
            book.set_identifier(str(uuid4()))

            title = proc_metadata.get("title") or f'Clipboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            book.set_title(title)
            book.set_language(proc_metadata.get("language", self.default_language))

            # Authors
            authors = proc_metadata.get("authors") or [self.default_author]
            for a in authors if isinstance(authors, list) else [authors]:
                book.add_author(a)

            # Metadata and type
            for key in ["date", "description", "source"]:
                val = proc_metadata.get(key)
                if val:
                    book.add_metadata("DC", key, str(val))
            book.add_metadata("DC", "type", f"clipboard_{format_type}")

            # CSS
            css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=css_style)
            book.add_item(css_item)

            epub_chapters = []

            # Optional static TOC page if provided in cached data
            if toc_html:
                toc_page = epub.EpubHtml(uid="toc", file_name="toc.xhtml", title="Table of Contents")
                page_content = toc_html.strip()
                if not (page_content.lower().startswith("<!doctype") or page_content.lower().startswith("<html")):
                    page_content = f"""<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
    <title>Table of Contents</title>
    <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/>
</head>
<body>
    {page_content}
</body>
</html>"""
                toc_page.content = page_content
                book.add_item(toc_page)
                epub_chapters.append(toc_page)
            for idx, chapter in enumerate(chapters, 1):
                html = epub.EpubHtml(uid=f"chapter_{idx}", file_name=f"chapter_{idx}.xhtml", title=chapter["title"])
                chapter_content = chapter["content"]
                if not (chapter_content.strip().startswith("<!DOCTYPE") or chapter_content.strip().startswith("<html")):
                    chapter_content = f"""<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
    <title>{chapter['title']}</title>
    <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/>
</head>
<body>
    <h1>{chapter['title']}</h1>
    {chapter_content}
</body>
</html>"""
                html.content = chapter_content
                book.add_item(html)
                epub_chapters.append(html)

            book.spine = ["nav"] + epub_chapters
            book.toc = epub_chapters
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            safe_title = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title)[:100]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}_cached.epub"
            filepath = self.output_dir / filename

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, epub.write_epub, str(filepath), book, {})

            logger.info(f"ePub created from cache: {filename}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Error creating ePub from cache: {e}", exc_info=True)
            return None

    async def _create_epub_async(self, processed: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        try:
            chapters = processed.get("chapters", [])
            proc_metadata = processed.get("metadata", {})
            css_style = processed.get("css", "")
            format_type = processed.get("format", "plain")
            toc_html = processed.get("toc_html")

            if not chapters:
                logger.warning("No chapters to convert")
                return None

            book = epub.EpubBook()
            book.set_identifier(str(uuid4()))

            title = metadata.get("title") or proc_metadata.get("title") or f'Clipboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            book.set_title(title)
            book.set_language(metadata.get("language", self.default_language))

            # Authors
            authors = metadata.get("authors") or proc_metadata.get("authors", [self.default_author])
            for a in authors if isinstance(authors, list) else [authors]:
                book.add_author(a)

            # Metadata
            for key, value in {**proc_metadata, **metadata}.items():
                if key in ["date", "description", "source"] and value:
                    book.add_metadata("DC", key, str(value))

            book.add_metadata("DC", "type", f"clipboard_{format_type}")

            css_item = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=css_style)
            book.add_item(css_item)

            epub_chapters = []

            # Optional static TOC page if provided by processor
            if toc_html:
                toc_page = epub.EpubHtml(uid="toc", file_name="toc.xhtml", title="Table of Contents")
                page_content = (toc_html or "").strip()
                if "\x00" in page_content:
                    page_content = page_content.replace("\x00", "")
                # Always wrap TOC in a minimal XHTML skeleton
                try:
                    inner = page_content
                    try:
                        from bs4 import BeautifulSoup  # type: ignore
                        soup = BeautifulSoup(page_content, 'html.parser')
                        if soup.body:
                            inner = soup.body.decode_contents() or inner
                    except Exception:
                        pass
                    page_content = f"""
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
    <meta charset=\"UTF-8\"/>
    <title>Table of Contents</title>
    <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/>
</head>
<body>
    {inner}
</body>
</html>"""
                except Exception:
                    # Fallback simple page
                    page_content = "<html xmlns=\"http://www.w3.org/1999/xhtml\"><head><meta charset=\"UTF-8\"/><title>Table of Contents</title><link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/></head><body></body></html>"
                toc_page.content = page_content.encode("utf-8", errors="ignore")
                book.add_item(toc_page)
                epub_chapters.append(toc_page)
            def _ensure_xhtml(doc_title: str, content: str) -> bytes:
                txt = (content or "").strip()
                # Strip NULs which break libxml encoders
                if "\x00" in txt:
                    txt = txt.replace("\x00", "")
                inner = txt
                # Extract body inner HTML if content is a full document to avoid nested <html>
                try:
                    from bs4 import BeautifulSoup  # type: ignore
                    soup = BeautifulSoup(txt, 'html.parser')
                    if soup.body:
                        inner = soup.body.decode_contents() or inner
                except Exception:
                    pass
                # Build minimal XHTML wrapper and force UTF-8 bytes
                wrapped = f"""
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
    <meta charset=\"UTF-8\"/>
    <title>{doc_title}</title>
    <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/>
</head>
<body>
    <h1>{doc_title}</h1>
    {inner}
</body>
</html>"""
                return wrapped.encode("utf-8", errors="ignore")

            for idx, chapter in enumerate(chapters, 1):
                html_item = epub.EpubHtml(uid=f"chapter_{idx}", file_name=f"chapter_{idx}.xhtml", title=chapter["title"])
                safe_bytes = _ensure_xhtml(chapter["title"], chapter["content"])
                html_item.content = safe_bytes
                book.add_item(html_item)
                epub_chapters.append(html_item)

            book.spine = ["nav"] + epub_chapters
            book.toc = epub_chapters
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            safe_title = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in title)[:100]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.epub"
            filepath = self.output_dir / filename

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, epub.write_epub, str(filepath), book, {})

            logger.info(f"ePub created: {filename}")
            logger.info(f"   Format: {format_type}")
            logger.info(f"   Chapters: {len(chapters)}")
            logger.info(f"   Size: {filepath.stat().st_size / 1024:.2f} KB")
            return str(filepath)
        except Exception as e:
            logger.error(f"Error creating ePub: {e}", exc_info=True)
            return None

    # --------- Hotkey callbacks ---------
    def _on_press(self, key):
        self.current_keys.add(key)

        if self.convert_hotkey.issubset(self.current_keys):
            logger.info("Convert hotkey triggered")
            self._trigger_conversion()
        elif self.accumulate_hotkey.issubset(self.current_keys):
            logger.info("Accumulate hotkey triggered")
            self._trigger_accumulate()
        elif self.combine_hotkey.issubset(self.current_keys):
            logger.info("Combine hotkey triggered")
            self._trigger_combine()

    def _on_release(self, key):
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

        if key == keyboard.Key.esc:
            logger.info("ESC pressed, stopping listener")
            # Avoid returning False here to prevent StopException bubbling through macOS event tap.
            # Stop the listener asynchronously instead.
            def _stop():
                try:
                    if self.listener:
                        self.listener.stop()
                except Exception:
                    pass

            t = threading.Thread(target=_stop, daemon=True)
            t.start()
            return

    def _trigger_conversion(self):
        def run():
            path = self.convert_clipboard_content()
            if path and self.conversion_callback:
                self.conversion_callback(path)

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _trigger_accumulate(self):
        t = threading.Thread(target=self.accumulate_current_clip, daemon=True)
        t.start()

    def _trigger_combine(self):
        t = threading.Thread(target=self.combine_accumulated_clips, daemon=True)
        t.start()

    # --------- Cleanup ---------
    def cleanup(self) -> None:
        try:
            self.stop_listening()
            if self.executor:
                self.executor.shutdown(wait=False)
            if self.cache:
                self.cache.cleanup_if_needed()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


__all__ = ["ClipboardToEpubConverter"]
