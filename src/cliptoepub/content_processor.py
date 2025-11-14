#!/usr/bin/env python3
"""
Content Processor Module for Clipboard to ePub
Handles intelligent content detection and conversion for different formats.

Moved under src/cliptoepub/ as part of Fase 8 to keep all core modules in the package.
"""

from __future__ import annotations

import re
import html
import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

import markdown2
from striprtf.striprtf import rtf_to_text
from bs4 import BeautifulSoup
import requests
from newspaper import Article

logger = logging.getLogger(__name__)


class ContentDetector:
    """Detects the format of clipboard content."""

    @staticmethod
    def detect_format(content: str) -> str:
        if not content:
            return "plain"
        content = content.strip()
        if ContentDetector._is_url(content):
            return "url"
        if content.startswith("{\\rtf"):
            return "rtf"
        if ContentDetector._is_html(content):
            return "html"
        if ContentDetector._is_markdown(content):
            return "markdown"
        return "plain"

    @staticmethod
    def _is_url(text: str) -> bool:
        if "\n" in text:
            return False
        try:
            result = urlparse(text)
            return all([result.scheme in ("http", "https"), result.netloc])
        except (ValueError, AttributeError) as e:
            logger.debug(f"Invalid URL format: {e}")
            return False

    @staticmethod
    def _is_html(text: str) -> bool:
        html_patterns = [
            r"<html[^>]*>",
            r"<body[^>]*>",
            r"<div[^>]*>",
            r"<p[^>]*>",
            r"<span[^>]*>",
            r"<h[1-6][^>]*>",
        ]
        for pattern in html_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        tag_count = len(re.findall(r"<[^>]+>", text))
        return tag_count >= 3

    @staticmethod
    def _is_markdown(text: str) -> bool:
        # Strong signal: at least one Markdown heading at the start of a line
        # (this is enough to treat the content as Markdown, even without other markers).
        if re.search(r"^#{1,6}\s+\S+", text, re.MULTILINE):
            return True

        markdown_patterns = [
            r"^#{1,6}\s+",
            r"\*\*[^*]+\*\*",
            r"__[^_]+__",
            r"\*[^*]+\*",
            r"_[^_]+_",
            r"^\s*[-*+]\s+",
            r"^\s*\d+\.\s+",
            r"\[([^\]]+)\]\(([^)]+)\)",
            r"!\[([^\]]*)\]\(([^)]+)\)",
            r"^```",
            r"`[^`]+`",
            r"^>\s+",
        ]
        score = 0
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE):
                score += 1
        return score >= 2


class ContentConverter:
    """Converts different content formats to HTML."""

    def __init__(self) -> None:
        self.css_templates = CSSTemplates()

    def convert(self, content: str, format_type: str) -> Tuple[str, Dict]:
        converters = {
            "url": self._convert_url,
            "markdown": self._convert_markdown,
            "html": self._convert_html,
            "rtf": self._convert_rtf,
            "plain": self._convert_plain,
        }
        converter = converters.get(format_type, self._convert_plain)
        html_content, metadata = converter(content)
        styled_html = self._apply_styling(html_content)
        return styled_html, metadata

    def _convert_url(self, url: str) -> Tuple[str, Dict]:
        metadata: Dict[str, Optional[str | list]] = {"source": url, "type": "web_article"}
        try:
            try:
                from newspaper import Config  # type: ignore

                cfg = Config()
                cfg.request_timeout = 10  # type: ignore[attr-defined]
                article = Article(url, config=cfg)
            except Exception:
                article = Article(url)
            article.download()
            article.parse()

            html_content = f"""
            <h1>{html.escape(article.title or 'Untitled Article')}</h1>
            <div class="article-meta">
                <p>Source: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                {f'<p>Authors: {html.escape(", ".join(article.authors))}</p>' if article.authors else ''}
                {f'<p>Published: {article.publish_date}</p>' if article.publish_date else ''}
            </div>
            <div class="article-content">
                {self._text_to_html_paragraphs(article.text)}
            </div>
            """

            metadata.update(
                {
                    "title": article.title,
                    "authors": article.authors,
                    "publish_date": str(article.publish_date) if article.publish_date else None,
                }
            )
            return html_content, metadata  # type: ignore[return-value]
        except Exception:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.find("title")
                title_text = title.text if title else "Web Page"
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = "\n".join(chunk for chunk in chunks if chunk)
                html_content = f"""
                <h1>{html.escape(title_text)}</h1>
                <p class="source">Source: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                <div class="content">
                    {self._text_to_html_paragraphs(text)}
                </div>
                """
                metadata["title"] = title_text
                return html_content, metadata  # type: ignore[return-value]
            except Exception as e2:
                error_html = f"""
                <h1>Error Loading URL</h1>
                <p>Could not load content from: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                <p>Error: {html.escape(str(e2))}</p>
                """
                return error_html, metadata  # type: ignore[return-value]

    def _convert_markdown(self, content: str) -> Tuple[str, Dict]:
        metadata: Dict[str, Optional[str]] = {"type": "markdown"}
        html_content = markdown2.markdown(
            content,
            extras=[
                "fenced-code-blocks",
                "tables",
                "strike",
                "footnotes",
                "smarty-pants",
                "header-ids",
                "code-friendly",
            ],
        )
        soup = BeautifulSoup(html_content, "html.parser")
        h1 = soup.find("h1")
        if h1:
            metadata["title"] = h1.get_text()
        return html_content, metadata  # type: ignore[return-value]

    def _convert_html(self, content: str) -> Tuple[str, Dict]:
        metadata: Dict[str, Optional[str]] = {"type": "html"}
        soup = BeautifulSoup(content, "html.parser")
        title = soup.find("title")
        if title:
            metadata["title"] = title.text
        for element in soup(["script", "style", "meta", "link"]):
            element.decompose()
        body = soup.find("body")
        html_content = str(body) if body else str(soup)
        return html_content, metadata  # type: ignore[return-value]

    def _convert_rtf(self, content: str) -> Tuple[str, Dict]:
        metadata: Dict[str, str] = {"type": "rtf"}
        try:
            plain_text = rtf_to_text(content)
            html_content = self._text_to_html_paragraphs(plain_text)
        except Exception:
            html_content = self._text_to_html_paragraphs(content)
        return html_content, metadata  # type: ignore[return-value]

    def _convert_plain(self, content: str) -> Tuple[str, Dict]:
        metadata: Dict[str, str] = {"type": "plain"}
        html_content = self._text_to_html_paragraphs(content)
        return html_content, metadata  # type: ignore[return-value]

    def _text_to_html_paragraphs(self, text: str) -> str:
        text = html.escape(text)
        paragraphs = text.split("\n\n")
        html_paragraphs: List[str] = []
        for para in paragraphs:
            para = para.strip()
            if para:
                para = para.replace("\n", "<br>")
                html_paragraphs.append(f"<p>{para}</p>")
        return "\n".join(html_paragraphs)

    def _apply_styling(self, html_content: str) -> str:
        if not re.search(r"<html[^>]*>", html_content, re.IGNORECASE):
            styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        {self.css_templates.get_default_css()}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
            """
        else:
            soup = BeautifulSoup(html_content, "html.parser")
            head = soup.find("head")
            if not head:
                head = soup.new_tag("head")
                soup.html.insert(0, head)
            style = soup.new_tag("style")
            style.string = self.css_templates.get_default_css()
            head.append(style)
            styled_html = str(soup)
        return styled_html


class ChapterSplitter:
    """Splits long content into chapters."""

    def __init__(self, words_per_chapter: int = 3000) -> None:
        self.words_per_chapter = words_per_chapter

    def split_content(self, html_content: str, title: Optional[str] = None) -> List[Dict]:
        soup = BeautifulSoup(html_content, "html.parser")
        headings = soup.find_all(["h1", "h2"])
        if len(headings) > 1:
            chapters = self._split_by_headings(soup, headings)
        else:
            chapters = self._split_by_word_count(soup, title)
        return chapters

    def _split_by_headings(self, soup: BeautifulSoup, headings: List) -> List[Dict]:
        chapters: List[Dict] = []
        for i, heading in enumerate(headings):
            chapter_title = heading.get_text().strip()
            chapter_content: List[str] = []
            current = heading
            while current:
                current = current.find_next_sibling()
                if current and current in headings:
                    break
                if current:
                    chapter_content.append(str(current))
            if chapter_content:
                chapters.append({"title": chapter_title, "content": "\n".join(chapter_content)})
        return chapters if chapters else [{"title": "Chapter 1", "content": str(soup)}]

    def _split_by_word_count(self, soup: BeautifulSoup, title: Optional[str] = None) -> List[Dict]:
        text = soup.get_text()
        words = text.split()
        if len(words) <= self.words_per_chapter:
            return [{"title": title or "Chapter 1", "content": str(soup)}]
        chapters: List[Dict] = []
        chapter_num = 1
        elements = soup.find_all(
            ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol"]
        )
        current_chapter_content: List[str] = []
        current_word_count = 0
        for element in elements:
            element_text = element.get_text()
            element_word_count = len(element_text.split())
            if current_word_count + element_word_count > self.words_per_chapter and current_chapter_content:
                chapters.append(
                    {"title": f"Chapter {chapter_num}", "content": "\n".join(current_chapter_content)}
                )
                chapter_num += 1
                current_chapter_content = []
                current_word_count = 0
            current_chapter_content.append(str(element))
            current_word_count += element_word_count
        if current_chapter_content:
            chapters.append(
                {"title": f"Chapter {chapter_num}", "content": "\n".join(current_chapter_content)}
            )
        return chapters


class TOCGenerator:
    """Generates Table of Contents for ePub."""

    def generate_toc_html(self, chapters: List[Dict], title: str = "Table of Contents") -> str:
        toc_items: List[str] = []
        for i, chapter in enumerate(chapters, 1):
            chapter_title = chapter.get("title", f"Chapter {i}")
            toc_items.append(f'<li><a href="#chapter_{i}">{html.escape(chapter_title)}</a></li>')
        toc_html = f"""
        <div class="toc">
            <h1>{html.escape(title)}</h1>
            <nav>
                <ul>
                    {''.join(toc_items)}
                </ul>
            </nav>
        </div>
        """
        return toc_html

    def generate_ncx_toc(self, chapters: List[Dict], book_title: str, book_id: str) -> str:
        nav_points: List[str] = []
        for i, chapter in enumerate(chapters, 1):
            chapter_title = chapter.get("title", f"Chapter {i}")
            nav_points.append(
                f"""
            <navPoint id="navpoint-{i}" playOrder="{i}">
                <navLabel>
                    <text>{html.escape(chapter_title)}</text>
                </navLabel>
                <content src="chapter_{i}.xhtml"/>
            </navPoint>
            """
            )
        ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
         "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
        <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
            <head>
                <meta name="dtb:uid" content="{html.escape(book_id)}"/>
                <meta name="dtb:depth" content="1"/>
                <meta name="dtb:totalPageCount" content="0"/>
                <meta name="dtb:maxPageNumber" content="0"/>
            </head>
            <docTitle>
                <text>{html.escape(book_title)}</text>
            </docTitle>
            <navMap>
                {''.join(nav_points)}
            </navMap>
        </ncx>
        """
        return ncx_content

    def add_anchors_to_chapters(self, chapters: List[Dict]) -> List[Dict]:
        updated_chapters: List[Dict] = []
        for i, chapter in enumerate(chapters, 1):
            content = chapter["content"]
            soup = BeautifulSoup(content, "html.parser")
            first_heading = soup.find(["h1", "h2", "h3"])
            if first_heading:
                first_heading["id"] = f"chapter_{i}"
            else:
                new_div = soup.new_tag("div", id=f"chapter_{i}")
                new_div.extend(soup.contents[:])
                soup.clear()
                soup.append(new_div)
            updated_chapter = chapter.copy()
            updated_chapter["content"] = str(soup)
            updated_chapters.append(updated_chapter)
        return updated_chapters


class CSSTemplates:
    """Provides CSS templates for ePub styling."""

    def get_default_css(self) -> str:
        return """
        /* Default ePub CSS Template */
        body {
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 1em;
            line-height: 1.6;
            margin: 1em;
            text-align: justify;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-weight: bold;
            line-height: 1.2;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            text-align: left;
        }

        h1 { font-size: 2em; }
        h2 { font-size: 1.75em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.25em; }
        h5 { font-size: 1.1em; }
        h6 { font-size: 1em; }

        p {
            margin: 0.5em 0 1em 0;
            text-indent: 1.5em;
        }

        p:first-of-type,
        h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p {
            text-indent: 0;
        }

        blockquote {
            margin: 1em 2em;
            font-style: italic;
            border-left: 3px solid #ccc;
            padding-left: 1em;
        }

        code {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background-color: #f4f4f4;
            padding: 0.1em 0.3em;
        }

        pre {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background-color: #f4f4f4;
            padding: 1em;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        ul, ol {
            margin: 1em 0;
            padding-left: 2em;
        }

        li {
            margin: 0.5em 0;
        }

        a {
            color: #0066cc;
            text-decoration: underline;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
        }
        """

    def get_minimal_css(self) -> str:
        return """
        /* Minimal ePub CSS Template */
        body {
            font-family: serif;
            font-size: 1em;
            line-height: 1.6;
            margin: 1em;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: serif;
            font-weight: normal;
            margin-top: 1.2em;
            margin-bottom: 0.5em;
        }

        p {
            margin: 0.75em 0;
        }

        a {
            color: inherit;
            text-decoration: underline;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
        }
        """

    def get_modern_css(self) -> str:
        return """
        /* Modern ePub CSS Template */
        /* Note: Remote font imports removed for ePub compatibility */

        body {
            font-family: 'Merriweather', Georgia, serif;
            font-size: 1em;
            font-weight: 300;
            line-height: 1.8;
            margin: 1.5em;
            color: #333;
            text-align: justify;
            hyphens: auto;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Open Sans', 'Helvetica Neue', sans-serif;
            font-weight: 600;
            line-height: 1.3;
            margin-top: 2em;
            margin-bottom: 0.75em;
            color: #111;
            text-align: left;
        }

        h1 {
            font-size: 2.5em;
            font-weight: 700;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 0.3em;
        }

        h2 { font-size: 2em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.25em; }

        p {
            margin: 0 0 1.5em 0;
            text-indent: 0;
        }

        p + p {
            text-indent: 1.5em;
        }

        blockquote {
            margin: 2em 0;
            padding: 1em 2em;
            background: linear-gradient(to right, #f7f7f7 0%, #ffffff 100%);
            border-left: 4px solid #4a90e2;
            font-style: italic;
            font-size: 1.05em;
        }

        code {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
            background: #f5f5f5;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            color: #d14;
        }

        pre {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 1.5em;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 0.9em;
            line-height: 1.4;
        }

        a {
            color: #4a90e2;
            text-decoration: none;
            border-bottom: 1px dotted #4a90e2;
            transition: color 0.3s ease;
        }

        a:hover {
            color: #357abd;
            border-bottom-style: solid;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 2em auto;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 4px;
        }

        .drop-cap {
            float: left;
            font-size: 4em;
            line-height: 1;
            margin: 0 0.1em 0 0;
            font-weight: 700;
            color: #4a90e2;
        }
        """

    def get_template(self, name: str = "default") -> str:
        """Get a CSS template by name, resolving templates/ relative to project root or bundle."""
        try:
            from pathlib import Path

            here = Path(__file__).resolve()
            candidates = [
                here.parent / "templates" / f"{name}.css",  # if templates/ is colocated with module
                here.parent.parent / "templates" / f"{name}.css",  # src/templates in source tree
                here.parent.parent.parent / "templates" / f"{name}.css",  # project/bundle root templates
            ]
            for p in candidates:
                try:
                    if p.exists() and p.is_file():
                        return p.read_text(encoding="utf-8")
                except Exception:
                    continue
        except Exception:
            pass

        templates = {
            "default": self.get_default_css,
            "minimal": self.get_minimal_css,
            "modern": self.get_modern_css,
        }
        return templates.get(name, self.get_default_css)()


def process_clipboard_content(content: str, options: Optional[Dict] = None) -> Dict:
    """
    Main function to process clipboard content.

    Returns a dict with chapters, metadata, css, format, and optional toc_html.
    """
    options = options or {}
    detector = ContentDetector()
    format_type = detector.detect_format(content)
    converter = ContentConverter()
    html_content, metadata = converter.convert(content, format_type)
    metadata["detected_format"] = format_type
    metadata["processing_date"] = datetime.now().isoformat()

    if options.get("split_chapters", True):
        splitter = ChapterSplitter(words_per_chapter=options.get("words_per_chapter", 3000))
        chapters = splitter.split_content(html_content, metadata.get("title", "Untitled"))
    else:
        chapters = [{"title": metadata.get("title", "Content"), "content": html_content}]

    toc_generator = TOCGenerator()
    toc_html = None
    if len(chapters) > 1 or options.get("force_toc", False):
        chapters = toc_generator.add_anchors_to_chapters(chapters)
        toc_html = toc_generator.generate_toc_html(chapters)

    css_template = options.get("css_template", "default")
    css = CSSTemplates().get_template(css_template)

    return {
        "chapters": chapters,
        "metadata": metadata,
        "css": css,
        "format": format_type,
        "toc_html": toc_html,
    }


__all__ = [
    "ContentDetector",
    "ContentConverter",
    "ChapterSplitter",
    "TOCGenerator",
    "CSSTemplates",
    "process_clipboard_content",
]
