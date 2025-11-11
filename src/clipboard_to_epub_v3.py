#!/usr/bin/env python3
"""
Clipboard to ePub - Phase 3 Enhanced Version
Converts clipboard content to ePub format with GUI support
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import threading

import pyperclip
from ebooklib import epub
from pynput import keyboard

# Add parent directory to path to import content_processor
sys.path.insert(0, str(Path(__file__).parent.parent))
from content_processor import process_clipboard_content
import paths

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ClipboardToEpub')

# Configuration defaults
DEFAULT_OUTPUT_DIR = paths.get_default_output_dir()

def _default_hotkey():
    try:
        if sys.platform.startswith('win') or sys.platform.startswith('linux'):
            return {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('e')}
        else:
            return {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('e')}
    except (AttributeError, KeyError) as e:
        # Fallback if pynput keys are not available on this platform
        logger.warning(f"Could not set platform-specific hotkey: {e}")
        return {keyboard.Key.shift, keyboard.KeyCode.from_char('e')}

DEFAULT_HOTKEY = _default_hotkey()


class ClipboardToEpubConverter:
    """Enhanced converter with GUI support and callbacks"""

    def __init__(self,
                 output_dir=None,
                 default_author="Unknown Author",
                 default_language="en",
                 default_style="default",
                 chapter_words=5000,
                 hotkey_combo=None):
        """
        Initialize the converter

        Args:
            output_dir: Path to output directory for ePub files
            default_author: Default author for ePubs
            default_language: Default language code
            default_style: CSS style to use (default, minimal, modern)
            chapter_words: Words per chapter for splitting
            hotkey_combo: Custom hotkey combination
        """
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.default_author = default_author
        self.default_language = default_language
        self.default_style = default_style
        self.chapter_words = chapter_words
        self.hotkey_combo = hotkey_combo or DEFAULT_HOTKEY

        self.current_keys = set()
        self.listener = None
        self.listening = False
        self.conversion_callback = None  # Callback for successful conversions

        self.ensure_output_dir()

    def ensure_output_dir(self):
        """Create output directory if it doesn't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")

    def convert_clipboard_content(self):
        """
        Convert clipboard content to ePub

        Returns:
            str: Path to created ePub file, or None if failed
        """
        try:
            # Get clipboard content
            clipboard_content = pyperclip.paste()

            if not clipboard_content or not clipboard_content.strip():
                logger.warning("Clipboard is empty")
                return None

            logger.info(f"Processing clipboard content ({len(clipboard_content)} chars)")

            # Process content with intelligent detection
            options = {
                'words_per_chapter': self.chapter_words,
                'css_template': self.default_style,
            }
            processed_data = process_clipboard_content(
                clipboard_content,
                options=options
            )

            # Extract processed components
            chapters = processed_data.get('chapters', [])
            metadata = processed_data.get('metadata', {})
            css_style = processed_data.get('css', '')
            format_type = processed_data.get('format', 'plain')

            if not chapters:
                logger.warning("No content to convert")
                return None

            # Create ePub
            book = epub.EpubBook()

            # Generate unique identifier
            book_id = str(uuid4())
            book.set_identifier(book_id)

            # Set metadata
            title = metadata.get('title', f'Clipboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            book.set_title(title)
            book.set_language(metadata.get('language', self.default_language))

            # Add authors
            authors = metadata.get('authors', [self.default_author])
            for author in authors:
                book.add_author(author)

            # Add additional metadata
            if metadata.get('date'):
                book.add_metadata('DC', 'date', metadata['date'])
            if metadata.get('description'):
                book.add_metadata('DC', 'description', metadata['description'])
            if metadata.get('source'):
                book.add_metadata('DC', 'source', metadata['source'])

            # Add format type as custom metadata
            book.add_metadata('DC', 'type', f'clipboard_{format_type}')

            # Add CSS
            css_item = epub.EpubItem(
                uid="style",
                file_name="style.css",
                media_type="text/css",
                content=css_style
            )
            book.add_item(css_item)

            # Create chapters
            epub_chapters = []
            toc_items = []

            for idx, chapter in enumerate(chapters, 1):
                chapter_id = f'chapter_{idx}'
                chapter_filename = f'chapter_{idx}.xhtml'

                # Create ePub chapter
                epub_chapter = epub.EpubHtml(
                    uid=chapter_id,
                    file_name=chapter_filename,
                    title=chapter['title']
                )

                # Set chapter content
                # Check if content already has full HTML structure
                chapter_content = chapter['content']
                if chapter_content.strip().startswith('<!DOCTYPE') or chapter_content.strip().startswith('<html'):
                    # Content already has full HTML, use as-is
                    epub_chapter.content = chapter_content
                else:
                    # Build chapter content with CSS reference
                    epub_chapter.content = f'''<!DOCTYPE html>
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

                # Add to book
                book.add_item(epub_chapter)
                epub_chapters.append(epub_chapter)
                toc_items.append(epub_chapter)

            # Set spine and table of contents
            book.spine = ['nav'] + epub_chapters
            book.toc = epub_chapters

            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Generate filename
            safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_'
                                for c in title)[:100]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.epub"
            filepath = self.output_dir / filename

            # Write ePub file
            epub.write_epub(str(filepath), book, {})

            logger.info(f"ePub created successfully: {filename}")
            logger.info(f"   Format detected: {format_type}")
            logger.info(f"   Chapters: {len(chapters)}")
            logger.info(f"   Style: {self.default_style}")
            logger.info(f"   Size: {filepath.stat().st_size / 1024:.2f} KB")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error creating ePub: {e}", exc_info=True)
            return None

    def on_press(self, key):
        """
        Handle key press events

        Args:
            key: The key that was pressed
        """
        self.current_keys.add(key)

        # Check if hotkey combination is pressed
        if self.hotkey_combo.issubset(self.current_keys):
            logger.info("Hotkey triggered!")

            # Run conversion in separate thread to avoid blocking
            def convert():
                filepath = self.convert_clipboard_content()
                if filepath and self.conversion_callback:
                    self.conversion_callback(filepath)

            thread = threading.Thread(target=convert)
            thread.daemon = True
            thread.start()

    def on_release(self, key):
        """
        Handle key release events

        Args:
            key: The key that was released
        """
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

        # Stop listener with ESC key
        if key == keyboard.Key.esc:
            logger.info("ESC pressed. Stopping listener...")
            self.stop_listening()
            return False

    def start_listening(self):
        """Start the keyboard listener"""
        if not self.listening:
            self.listening = True
            logger.info("Starting keyboard listener...")

            self.listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self.listener.start()

            # Keep the listener running
            self.listener.join()

    def stop_listening(self):
        """Stop the keyboard listener"""
        if self.listening and self.listener:
            self.listening = False
            logger.info("Stopping keyboard listener...")
            self.listener.stop()

    def run_cli(self):
        """
        Run in CLI mode (for backward compatibility)
        """
        print("=" * 60)
        print("Clipboard to ePub Converter - Phase 3")
        print("=" * 60)
        print("FEATURES:")
        print("  - Menu bar application")
        print("  - Automatic format detection")
        print("  - Smart content conversion")
        print("  - Chapter splitting")
        print("  - Table of contents")
        print("  - Professional CSS styling")
        print("-" * 60)
        print(f"Output directory: {self.output_dir}")
        hotkey_label = "Ctrl + Shift + E" if sys.platform.startswith('win') or sys.platform.startswith('linux') else "Cmd + Shift + E"
        print(f"Hotkey: {hotkey_label}")
        print("Press ESC to quit")
        print("-" * 60)
        print("Listening for hotkey...")

        # Set CLI callback
        def cli_callback(filepath):
            if filepath:
                print(f"\n[SUCCESS] ePub created: {os.path.basename(filepath)}")
            else:
                print("\n[ERROR] Failed to create ePub")

        self.conversion_callback = cli_callback

        # Start listening
        self.start_listening()

        print("\nGoodbye!")


def main():
    """Main entry point for CLI"""
    try:
        # Check if custom output directory is provided
        output_dir = None
        if len(sys.argv) > 1:
            output_dir = sys.argv[1]
            print(f"Using custom output directory: {output_dir}")

        # Create and run converter
        converter = ClipboardToEpubConverter(output_dir=output_dir)
        converter.run_cli()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
