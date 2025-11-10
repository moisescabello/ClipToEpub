#!/usr/bin/env python3
"""
Clipboard to ePub - Phase 2 Enhanced Version
Converts clipboard content to ePub format with intelligent content processing
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
import paths
from uuid import uuid4

import pyperclip
from ebooklib import epub
from pynput import keyboard

# Add parent directory to path to import content_processor
sys.path.insert(0, str(Path(__file__).parent.parent))
from content_processor import process_clipboard_content, TOCGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ClipboardToEpub')

# Configuration
DEFAULT_OUTPUT_DIR = paths.get_default_output_dir()
HOTKEY_COMBINATION = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('e')}

class EnhancedClipboardToEpubConverter:
    """Enhanced converter with intelligent content processing"""

    def __init__(self, output_dir=None):
        """
        Initialize the converter

        Args:
            output_dir: Path to output directory for ePub files
        """
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.current_keys = set()
        self.ensure_output_dir()

    def ensure_output_dir(self):
        """Create output directory if it doesn't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")

    def get_clipboard_content(self):
        """
        Get content from clipboard

        Returns:
            str: Clipboard content or None if empty/error
        """
        try:
            content = pyperclip.paste()
            if not content or content.strip() == "":
                logger.warning("Clipboard is empty")
                return None
            return content
        except Exception as e:
            logger.error(f"Error reading clipboard: {e}")
            return None

    def create_enhanced_epub(self, content):
        """
        Create enhanced ePub with intelligent content processing

        Args:
            content: Text content to convert to ePub

        Returns:
            Path: Path to created ePub file or None if error
        """
        try:
            # Process content with intelligent detection and conversion
            logger.info("Processing content with intelligent detection...")
            processed = process_clipboard_content(content, {
                'split_chapters': True,
                'words_per_chapter': 3000,
                'css_template': 'default'
            })

            # Create book instance
            book = epub.EpubBook()

            # Generate metadata
            timestamp = datetime.now()
            metadata = processed['metadata']

            # Use extracted title if available, otherwise generate one
            if metadata.get('title'):
                title = metadata['title']
                filename = f"{title.replace(' ', '_').replace('/', '-')[:50]}_{timestamp.strftime('%Y%m%d_%H%M%S')}.epub"
            else:
                title = f"Clipboard Capture - {timestamp.strftime('%Y-%m-%d %H:%M')}"
                filename = f"clipboard_{timestamp.strftime('%Y%m%d_%H%M%S')}.epub"

            # Set metadata
            book.set_identifier(str(uuid4()))
            book.set_title(title)
            book.set_language('en')

            # Add author if available
            if metadata.get('authors'):
                for author in metadata['authors']:
                    book.add_author(author)

            # Add description based on detected format
            format_type = processed['format']
            description = f"Generated from {format_type} content in clipboard"
            if metadata.get('source'):
                description += f" - Source: {metadata['source']}"
            book.add_metadata('DC', 'description', description)
            book.add_metadata('DC', 'date', timestamp.isoformat())
            book.add_metadata(None, 'meta', '', {'name': 'content-type', 'content': format_type})

            # Add CSS styling
            css_item = epub.EpubItem(
                uid="style",
                file_name="style.css",
                media_type="text/css",
                content=processed['css']
            )
            book.add_item(css_item)

            # Create chapters from processed content
            epub_chapters = []
            chapters_data = processed['chapters']

            # Add table of contents as first chapter if available
            if processed.get('toc_html') and len(chapters_data) > 1:
                toc_chapter = epub.EpubHtml(
                    title='Table of Contents',
                    file_name='toc.xhtml',
                    lang='en'
                )
                toc_chapter.content = processed['toc_html']
                toc_chapter.add_item(css_item)
                book.add_item(toc_chapter)
                epub_chapters.append(toc_chapter)

            # Add content chapters
            for i, chapter_data in enumerate(chapters_data, 1):
                chapter = epub.EpubHtml(
                    title=chapter_data['title'],
                    file_name=f'chapter_{i}.xhtml',
                    lang='en'
                )

                # Wrap chapter content in proper HTML structure
                chapter_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{chapter_data['title']}</title>
                    <link rel="stylesheet" type="text/css" href="style.css"/>
                </head>
                <body>
                    <h1 id="chapter_{i}">{chapter_data['title']}</h1>
                    {chapter_data['content']}
                </body>
                </html>
                """

                chapter.content = chapter_html
                chapter.add_item(css_item)
                book.add_item(chapter)
                epub_chapters.append(chapter)

            # Add navigation
            book.toc = epub_chapters
            book.spine = ['nav'] + epub_chapters

            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Write ePub file
            output_path = self.output_dir / filename
            epub.write_epub(output_path, book)

            logger.info(f"Enhanced ePub created successfully: {output_path}")
            logger.info(f"Format detected: {format_type}")
            logger.info(f"Number of chapters: {len(chapters_data)}")

            return output_path

        except Exception as e:
            logger.error(f"Error creating enhanced ePub: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def convert_clipboard_to_epub(self):
        """
        Main conversion function - get clipboard content and create enhanced ePub

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Starting enhanced clipboard to ePub conversion...")

        # Get clipboard content
        content = self.get_clipboard_content()
        if not content:
            self.notify("Clipboard is empty. Nothing to convert.")
            return False

        # Create enhanced ePub
        output_path = self.create_enhanced_epub(content)
        if output_path:
            self.notify(f"Enhanced ePub created: {output_path.name}")
            return True
        else:
            self.notify("Failed to create ePub. Check logs for details.")
            return False

    def notify(self, message):
        """
        Send notification to user

        Args:
            message: Notification message
        """
        print(f"\n📚 {message}")
        logger.info(f"Notification: {message}")

    def on_press(self, key):
        """
        Handle key press events

        Args:
            key: The key that was pressed
        """
        self.current_keys.add(key)

        # Check if hotkey combination is pressed
        if all(k in self.current_keys for k in HOTKEY_COMBINATION):
            logger.info("Hotkey combination detected!")
            self.convert_clipboard_to_epub()
            # Clear the current keys to avoid repeated triggers
            self.current_keys.clear()

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
            logger.info("ESC pressed. Stopping...")
            return False

    def run(self):
        """
        Start the keyboard listener and run the application
        """
        print("=" * 60)
        print("📋 Clipboard to ePub Converter - Phase 2 Enhanced")
        print("=" * 60)
        print("✨ NEW FEATURES:")
        print("  • Automatic format detection (Markdown, HTML, RTF, URLs)")
        print("  • Smart content conversion")
        print("  • Chapter splitting for long content")
        print("  • Table of contents generation")
        print("  • Professional CSS styling")
        print("-" * 60)
        print(f"Output directory: {self.output_dir}")
        print(f"Hotkey: Cmd + Shift + E")
        print("Press ESC to quit")
        print("-" * 60)
        print("Listening for hotkey...")

        # Start keyboard listener
        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            listener.join()

        print("\nGoodbye! 👋")


def main():
    """Main entry point"""
    try:
        # Check if custom output directory is provided
        output_dir = sys.argv[1] if len(sys.argv) > 1 else None

        # Create and run enhanced converter
        converter = EnhancedClipboardToEpubConverter(output_dir)
        converter.run()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
