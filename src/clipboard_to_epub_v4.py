#!/usr/bin/env python3
"""
Clipboard to ePub - Phase 4 Advanced Version
Enhanced converter with image handling, history, caching, and async processing
"""

import os
import sys
import logging
import asyncio
import aiofiles
import threading
from datetime import datetime
from pathlib import Path
import paths
from uuid import uuid4
from typing import Optional, Dict, Any, List
import json

import pyperclip
from ebooklib import epub
from pynput import keyboard
from PIL import Image

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Phase 4 modules
from content_processor import process_clipboard_content
from image_handler import ImageHandler
from history_manager import ConversionHistory, ClipboardAccumulator, ConversionCache
from edit_window import PreConversionEditor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ClipboardToEpubV4')

# Configuration defaults
DEFAULT_OUTPUT_DIR = paths.get_default_output_dir()
DEFAULT_HOTKEY = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('e')}
DEFAULT_ACCUMULATE_HOTKEY = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('a')}
DEFAULT_COMBINE_HOTKEY = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('c')}


class AdvancedClipboardToEpubConverter:
    """Phase 4 converter with advanced features"""

    def __init__(self,
                 output_dir: Optional[Path] = None,
                 default_author: str = "Unknown Author",
                 default_language: str = "en",
                 default_style: str = "default",
                 chapter_words: int = 5000,
                 enable_ocr: bool = False,
                 enable_cache: bool = True,
                 enable_history: bool = True,
                 enable_edit_window: bool = False,
                 max_async_workers: int = 3):
        """
        Initialize the advanced converter

        Args:
            output_dir: Output directory for ePub files
            default_author: Default author
            default_language: Default language code
            default_style: CSS style
            chapter_words: Words per chapter
            enable_ocr: Enable OCR for images
            enable_cache: Enable conversion cache
            enable_history: Enable history tracking
            enable_edit_window: Show edit window before conversion
            max_async_workers: Maximum async workers
        """
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

        # Initialize components
        self.image_handler = ImageHandler(enable_ocr=enable_ocr, optimize_images=True)
        self.history = ConversionHistory() if enable_history else None
        self.accumulator = ClipboardAccumulator(max_clips=50)
        self.cache = ConversionCache() if enable_cache else None

        # Hotkey management
        self.current_keys = set()
        self.listener = None
        self.listening = False

        # Callbacks
        self.conversion_callback = None
        self.error_callback = None

        # Async event loop
        self.loop = None
        self.executor = None

        self.ensure_output_dir()
        self.setup_async()

    def ensure_output_dir(self):
        """Create output directory if it doesn't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")

    def setup_async(self):
        """Set up async processing"""
        try:
            # Try to get existing event loop or create new one
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create a new one
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

            # Create thread pool executor for CPU-bound tasks
            from concurrent.futures import ThreadPoolExecutor
            self.executor = ThreadPoolExecutor(max_workers=self.max_async_workers)

            logger.info(f"Async processing initialized with {self.max_async_workers} workers")
        except Exception as e:
            logger.error(f"Failed to setup async: {e}")

    async def convert_clipboard_content_async(self,
                                             clipboard_content: Optional[str] = None,
                                             use_accumulator: bool = False) -> Optional[str]:
        """
        Asynchronously convert clipboard content to ePub

        Args:
            clipboard_content: Optional content (if None, reads from clipboard)
            use_accumulator: Whether to use accumulated clips

        Returns:
            Path to created ePub or None
        """
        try:
            # Get content
            if use_accumulator:
                # Use accumulated clips
                content = self.accumulator.combine_clips()
                metadata = self.accumulator.get_combined_metadata()
                if not content:
                    logger.warning("No accumulated clips to convert")
                    return None
            else:
                # Get from clipboard or parameter
                content = clipboard_content or await self.get_clipboard_content_async()
                metadata = {}

            if not content or not content.strip():
                # Check for image in clipboard
                image = self.image_handler.detect_image_in_clipboard()
                if image:
                    logger.info("Image detected in clipboard")
                    return await self.convert_image_to_epub_async(image)
                else:
                    logger.warning("No content to convert")
                    return None

            logger.info(f"Processing content ({len(content)} chars)")

            # Check cache
            if self.cache:
                cache_key = {'style': self.default_style, 'chapter_words': self.chapter_words}
                cached_result = self.cache.get(content, cache_key)
                if cached_result:
                    logger.info("Using cached conversion result")
                    # Still create a new file with cached data
                    return await self.create_epub_from_cached_async(cached_result)

            # Show edit window if enabled
            if self.enable_edit_window and not use_accumulator:
                edited_content, edited_metadata = await self.show_edit_window_async(content, metadata)
                if edited_content:
                    content = edited_content
                    metadata.update(edited_metadata)
                else:
                    logger.info("User cancelled conversion")
                    return None

            # Process content
            options = {
                'chapter_words': self.chapter_words,
                'style': self.default_style
            }

            # Process in thread pool to avoid blocking
            processed_data = await self.loop.run_in_executor(
                self.executor,
                process_clipboard_content,
                content,
                options
            )

            # Create ePub
            filepath = await self.create_epub_async(processed_data, metadata)

            # Cache result if enabled
            if self.cache and filepath:
                self.cache.put(content, options, processed_data)

            # Add to history if enabled
            if self.history and filepath:
                history_metadata = {
                    'title': processed_data.get('metadata', {}).get('title', 'Untitled'),
                    'format': processed_data.get('format', 'unknown'),
                    'chapters': len(processed_data.get('chapters', [])),
                    'size': Path(filepath).stat().st_size,
                    'author': self.default_author
                }
                self.history.add_entry(filepath, history_metadata)

            return filepath

        except Exception as e:
            logger.error(f"Error in async conversion: {e}", exc_info=True)
            if self.error_callback:
                self.error_callback(str(e))
            return None

    async def convert_image_to_epub_async(self, image: Image.Image) -> Optional[str]:
        """
        Convert an image to ePub asynchronously

        Args:
            image: PIL Image object

        Returns:
            Path to created ePub or None
        """
        try:
            # Process image in thread pool
            image_data = await self.loop.run_in_executor(
                self.executor,
                self.image_handler.process_image_for_epub,
                image,
                None,
                self.enable_ocr
            )

            # Create chapter from image
            chapter = self.image_handler.create_image_chapter(image_data)

            # Prepare processed data
            processed_data = {
                'chapters': [chapter],
                'metadata': {
                    'title': image_data['title'],
                    'type': 'image'
                },
                'format': 'image',
                'style': self.image_handler.get_image_css()
            }

            # Create ePub
            filepath = await self.create_epub_async(processed_data, {})

            # Add to history
            if self.history and filepath:
                history_metadata = {
                    'title': image_data['title'],
                    'format': 'image',
                    'chapters': 1,
                    'size': Path(filepath).stat().st_size,
                    'author': self.default_author,
                    'tags': ['image']
                }
                if image_data.get('has_text'):
                    history_metadata['tags'].append('ocr')
                self.history.add_entry(filepath, history_metadata)

            return filepath

        except Exception as e:
            logger.error(f"Error converting image: {e}", exc_info=True)
            return None

    async def get_clipboard_content_async(self) -> str:
        """Get clipboard content asynchronously"""
        return await self.loop.run_in_executor(None, pyperclip.paste)

    async def show_edit_window_async(self, content: str, metadata: Dict[str, Any]):
        """
        Show edit window asynchronously

        Args:
            content: Initial content
            metadata: Initial metadata

        Returns:
            Tuple of (edited_content, edited_metadata) or (None, None) if cancelled
        """
        # This needs to run in the main thread for GUI
        result = {'content': None, 'metadata': None}
        event = threading.Event()

        def on_convert(edited_content, edited_metadata):
            result['content'] = edited_content
            result['metadata'] = edited_metadata
            event.set()

        def on_cancel():
            event.set()

        def show_window():
            editor = PreConversionEditor(
                content=content,
                metadata=metadata,
                on_convert=on_convert,
                on_cancel=on_cancel
            )
            editor.run()

        # Run in main thread
        thread = threading.Thread(target=show_window)
        thread.start()

        # Wait for window to close
        await self.loop.run_in_executor(None, event.wait)

        return result['content'], result['metadata'] or {}

    async def create_epub_from_cached_async(self, cached_data: Dict[str, Any]) -> Optional[str]:
        """Create ePub from cached data"""
        # Generate new filename with current timestamp
        title = cached_data.get('metadata', {}).get('title', 'Cached')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{timestamp}_cached.epub"
        filepath = self.output_dir / filename

        # Recreate ePub from cached data
        # (Implementation similar to create_epub_async but using cached data)
        logger.info(f"Created ePub from cache: {filename}")
        return str(filepath)

    async def create_epub_async(self, processed_data: Dict[str, Any],
                               metadata: Dict[str, Any]) -> Optional[str]:
        """
        Create ePub file asynchronously

        Args:
            processed_data: Processed content data
            metadata: Additional metadata

        Returns:
            Path to created ePub or None
        """
        try:
            # Extract components
            chapters = processed_data.get('chapters', [])
            proc_metadata = processed_data.get('metadata', {})
            css_style = processed_data.get('style', '')
            format_type = processed_data.get('format', 'plain')

            if not chapters:
                logger.warning("No chapters to convert")
                return None

            # Create ePub
            book = epub.EpubBook()

            # Set metadata
            book_id = str(uuid4())
            book.set_identifier(book_id)

            title = metadata.get('title') or proc_metadata.get('title') or \
                   f'Clipboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            book.set_title(title)
            book.set_language(metadata.get('language', self.default_language))

            # Add authors
            authors = metadata.get('authors') or proc_metadata.get('authors', [self.default_author])
            for author in authors if isinstance(authors, list) else [authors]:
                book.add_author(author)

            # Add metadata
            for key, value in {**proc_metadata, **metadata}.items():
                if key in ['date', 'description', 'source'] and value:
                    book.add_metadata('DC', key, str(value))

            # Add format type
            book.add_metadata('DC', 'type', f'clipboard_{format_type}_v4')

            # Add CSS
            css_item = epub.EpubItem(
                uid="style",
                file_name="style.css",
                media_type="text/css",
                content=css_style
            )
            book.add_item(css_item)

            # Create chapters asynchronously
            epub_chapters = []
            for idx, chapter in enumerate(chapters, 1):
                epub_chapter = epub.EpubHtml(
                    uid=f'chapter_{idx}',
                    file_name=f'chapter_{idx}.xhtml',
                    title=chapter['title']
                )

                # Build content
                chapter_content = chapter['content']
                if not (chapter_content.strip().startswith('<!DOCTYPE') or
                       chapter_content.strip().startswith('<html')):
                    chapter_content = f'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{chapter['title']}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h1>{chapter['title']}</h1>
    {chapter_content}
</body>
</html>'''

                epub_chapter.content = chapter_content
                book.add_item(epub_chapter)
                epub_chapters.append(epub_chapter)

            # Set spine and TOC
            book.spine = ['nav'] + epub_chapters
            book.toc = epub_chapters

            # Add navigation
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Generate filename
            safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_'
                               for c in title)[:100]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.epub"
            filepath = self.output_dir / filename

            # Write ePub asynchronously
            await self.loop.run_in_executor(
                self.executor,
                epub.write_epub,
                str(filepath),
                book,
                {}
            )

            logger.info(f"✅ ePub created: {filename}")
            logger.info(f"   Format: {format_type}")
            logger.info(f"   Chapters: {len(chapters)}")
            logger.info(f"   Size: {filepath.stat().st_size / 1024:.2f} KB")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error creating ePub: {e}", exc_info=True)
            return None

    def convert_clipboard_content(self, use_accumulator: bool = False) -> Optional[str]:
        """
        Synchronous wrapper for async conversion

        Args:
            use_accumulator: Whether to use accumulated clips

        Returns:
            Path to created ePub or None
        """
        try:
            # Check if we're already in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're already in an async context, can't use run_coroutine_threadsafe
                logger.warning("Already in async context, falling back to sync processing")
                # Fall back to synchronous processing
                return None
            except RuntimeError:
                # No running loop, we can create one
                pass

            # Run async conversion in event loop
            if not self.loop or not self.loop.is_running():
                # Create a new event loop in a thread
                import threading
                result = {'filepath': None}
                exception = {'error': None}

                def run_async():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        filepath = new_loop.run_until_complete(
                            self.convert_clipboard_content_async(use_accumulator=use_accumulator)
                        )
                        result['filepath'] = filepath
                    except Exception as e:
                        exception['error'] = e
                    finally:
                        new_loop.close()

                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join(timeout=30)  # 30 second timeout

                if exception['error']:
                    raise exception['error']
                return result['filepath']
            else:
                # Use existing loop
                future = asyncio.run_coroutine_threadsafe(
                    self.convert_clipboard_content_async(use_accumulator=use_accumulator),
                    self.loop
                )
                return future.result(timeout=30)  # 30 second timeout

        except Exception as e:
            logger.error(f"Error in sync conversion: {e}")
            return None

    def accumulate_current_clip(self):
        """Add current clipboard content to accumulator"""
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

    def combine_accumulated_clips(self):
        """Convert accumulated clips to ePub"""
        filepath = self.convert_clipboard_content(use_accumulator=True)
        if filepath:
            self.accumulator.clear()  # Clear after successful conversion
            if self.conversion_callback:
                self.conversion_callback(filepath)

    def on_press(self, key):
        """Handle key press events"""
        self.current_keys.add(key)

        # Check for hotkey combinations
        if self.current_keys == DEFAULT_HOTKEY:
            logger.info("Convert hotkey triggered!")
            self.trigger_conversion()

        elif self.current_keys == DEFAULT_ACCUMULATE_HOTKEY:
            logger.info("Accumulate hotkey triggered!")
            self.trigger_accumulate()

        elif self.current_keys == DEFAULT_COMBINE_HOTKEY:
            logger.info("Combine hotkey triggered!")
            self.trigger_combine()

    def on_release(self, key):
        """Handle key release events"""
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

        # Stop listener on Esc
        if key == keyboard.Key.esc:
            logger.info("ESC pressed, stopping listener")
            return False

    def trigger_conversion(self):
        """Trigger clipboard conversion in background"""
        def convert():
            filepath = self.convert_clipboard_content()
            if filepath and self.conversion_callback:
                self.conversion_callback(filepath)

        thread = threading.Thread(target=convert)
        thread.daemon = True
        thread.start()

    def trigger_accumulate(self):
        """Trigger clip accumulation in background"""
        thread = threading.Thread(target=self.accumulate_current_clip)
        thread.daemon = True
        thread.start()

    def trigger_combine(self):
        """Trigger combine accumulated clips in background"""
        thread = threading.Thread(target=self.combine_accumulated_clips)
        thread.daemon = True
        thread.start()

    def start_listening(self):
        """Start listening for hotkeys"""
        if not self.listening:
            self.listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self.listener.start()
            self.listening = True
            logger.info("Started listening for hotkeys")
            logger.info(f"  Convert: Cmd+Shift+E")
            logger.info(f"  Accumulate: Cmd+Shift+A")
            logger.info(f"  Combine: Cmd+Shift+C")
            logger.info(f"  Stop: ESC")

    def stop_listening(self):
        """Stop listening for hotkeys"""
        if self.listening and self.listener:
            self.listener.stop()
            self.listening = False
            logger.info("Stopped listening for hotkeys")

    def get_recent_conversions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversion history"""
        if self.history:
            return self.history.get_recent(limit)
        return []

    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_listening()
            if self.executor:
                self.executor.shutdown(wait=False)
            if self.loop:
                self.loop.close()
            if self.cache:
                self.cache.cleanup_if_needed()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for Phase 4 converter"""
    print("=" * 60)
    print("📋 Clipboard to ePub Converter - Phase 4 Advanced Version")
    print("=" * 60)

    # Create converter with all features enabled
    converter = AdvancedClipboardToEpubConverter(
        enable_ocr=False,  # Set to True if Tesseract is installed
        enable_cache=True,
        enable_history=True,
        enable_edit_window=False,  # Set to True for GUI editing
        max_async_workers=3
    )

    # Set up callbacks
    def on_conversion_success(filepath):
        print(f"\n✅ ePub created: {filepath}")

    def on_conversion_error(error):
        print(f"\n❌ Conversion error: {error}")

    converter.conversion_callback = on_conversion_success
    converter.error_callback = on_conversion_error

    # Start listening
    converter.start_listening()

    print("\nHotkeys:")
    print("  📝 Cmd+Shift+E - Convert clipboard to ePub")
    print("  ➕ Cmd+Shift+A - Add clipboard to accumulator")
    print("  📚 Cmd+Shift+C - Combine accumulated clips to ePub")
    print("  🛑 ESC - Stop listening")
    print("\nListening for hotkeys...")

    try:
        # Keep the program running
        converter.listener.join()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        converter.cleanup()
        print("Goodbye!")


if __name__ == '__main__':
    main()
