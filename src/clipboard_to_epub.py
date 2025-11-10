#!/usr/bin/env python3
"""
Clipboard to ePub - Phase 1 Prototype
Converts clipboard content to ePub format with a global hotkey
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ClipboardToEpub')

# Configuration
DEFAULT_OUTPUT_DIR = paths.get_default_output_dir()
HOTKEY_COMBINATION = {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('e')}

class ClipboardToEpubConverter:
    """Main converter class that handles clipboard to ePub conversion"""

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

    def create_epub(self, content):
        """
        Create ePub from text content

        Args:
            content: Text content to convert to ePub

        Returns:
            Path: Path to created ePub file or None if error
        """
        try:
            # Create book instance
            book = epub.EpubBook()

            # Generate metadata
            timestamp = datetime.now()
            title = f"Clipboard Capture - {timestamp.strftime('%Y-%m-%d %H:%M')}"
            filename = f"clipboard_{timestamp.strftime('%Y%m%d_%H%M%S')}.epub"

            # Set metadata
            book.set_identifier(str(uuid4()))
            book.set_title(title)
            book.set_language('en')
            book.add_metadata('DC', 'description', 'Generated from clipboard content')
            book.add_metadata('DC', 'date', timestamp.isoformat())

            # Create chapter with content
            chapter = epub.EpubHtml(
                title='Content',
                file_name='content.xhtml',
                lang='en'
            )

            # Convert plain text to HTML with proper formatting
            html_content = self.text_to_html(content)
            chapter.content = html_content

            # Add chapter to book
            book.add_item(chapter)

            # Add navigation
            book.toc = (chapter,)
            book.spine = ['nav', chapter]

            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Add basic CSS for better readability
            style = '''
            body {
                font-family: Georgia, serif;
                font-size: 1em;
                line-height: 1.6;
                margin: 1em;
            }
            p {
                text-indent: 1.5em;
                margin: 0.5em 0;
            }
            h1, h2, h3 {
                font-family: Helvetica, Arial, sans-serif;
                margin: 1em 0 0.5em 0;
            }
            pre {
                background-color: #f5f5f5;
                padding: 1em;
                overflow-x: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }
            '''

            css_item = epub.EpubItem(
                uid="style",
                file_name="style.css",
                media_type="text/css",
                content=style
            )
            book.add_item(css_item)
            chapter.add_item(css_item)

            # Write ePub file
            output_path = self.output_dir / filename
            epub.write_epub(output_path, book)

            logger.info(f"ePub created successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error creating ePub: {e}")
            return None

    def text_to_html(self, text):
        """
        Convert plain text to HTML with basic formatting

        Args:
            text: Plain text content

        Returns:
            str: HTML formatted content
        """
        # Escape HTML special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')

        # Split into paragraphs
        paragraphs = text.split('\n\n')

        html_parts = ['<html><head><title>Content</title></head><body>']

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Check if it's a code block (starts with 4 spaces or tab)
            if paragraph.startswith('    ') or paragraph.startswith('\t'):
                html_parts.append(f'<pre>{paragraph}</pre>')
            # Check if it's a heading (simple heuristic)
            elif len(paragraph) < 50 and not paragraph.endswith('.'):
                html_parts.append(f'<h2>{paragraph}</h2>')
            else:
                # Regular paragraph - preserve line breaks within paragraph
                formatted = paragraph.replace('\n', '<br/>')
                html_parts.append(f'<p>{formatted}</p>')

        html_parts.append('</body></html>')

        return '\n'.join(html_parts)

    def convert_clipboard_to_epub(self):
        """
        Main conversion function - get clipboard content and create ePub

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Starting clipboard to ePub conversion...")

        # Get clipboard content
        content = self.get_clipboard_content()
        if not content:
            self.notify("Clipboard is empty. Nothing to convert.")
            return False

        # Create ePub
        output_path = self.create_epub(content)
        if output_path:
            self.notify(f"ePub created: {output_path.name}")
            return True
        else:
            self.notify("Failed to create ePub. Check logs for details.")
            return False

    def notify(self, message):
        """
        Send notification to user (console for now, system notification in Phase 3)

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
        print("📋 Clipboard to ePub Converter - Phase 1 Prototype")
        print("=" * 60)
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

        # Create and run converter
        converter = ClipboardToEpubConverter(output_dir)
        converter.run()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
