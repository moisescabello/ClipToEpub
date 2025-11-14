import pytest

content_processor = pytest.importorskip("cliptoepub.content_processor")

ContentDetector = content_processor.ContentDetector
ContentConverter = content_processor.ContentConverter
process_clipboard_content = content_processor.process_clipboard_content


def test_content_detector_detects_basic_formats() -> None:
    assert ContentDetector.detect_format("") == "plain"
    assert ContentDetector.detect_format("Just some text") == "plain"
    assert ContentDetector.detect_format("https://example.com") == "url"
    assert ContentDetector.detect_format("http://example.com") == "url"
    assert ContentDetector.detect_format("{\\rtf1\\ansi\n...") == "rtf"


def test_content_detector_distinguishes_markdown_and_html() -> None:
    markdown_text = "# Title\n\nSome **bold** text."
    html_text = "<html><body><h1>Title</h1><p>Text</p></body></html>"

    assert ContentDetector.detect_format(markdown_text) == "markdown"
    assert ContentDetector.detect_format(html_text) == "html"


def test_convert_html_strips_unsafe_tags_and_keeps_title() -> None:
    raw_html = """
    <html>
      <head>
        <title>Sample Page</title>
        <meta charset="utf-8">
        <link rel="stylesheet" href="style.css">
        <script>console.log("x")</script>
        <style>body { background: red; }</style>
      </head>
      <body>
        <p>Hello</p>
        <script>alert("bad")</script>
      </body>
    </html>
    """
    converter = ContentConverter()
    html_content, metadata = converter._convert_html(raw_html)

    assert metadata["type"] == "html"
    assert metadata["title"] == "Sample Page"
    assert "<script" not in html_content.lower()
    assert "<style" not in html_content.lower()
    assert "<meta" not in html_content.lower()
    assert "<link" not in html_content.lower()
    assert "<p>Hello</p>" in html_content


def test_process_clipboard_content_sets_metadata_and_toc_when_forced() -> None:
    content = "# Heading\n\nFirst paragraph.\n\nSecond paragraph."
    result = process_clipboard_content(
        content,
        options={"split_chapters": True, "force_toc": True, "css_template": "minimal"},
    )

    metadata = result["metadata"]
    chapters = result["chapters"]
    toc_html = result["toc_html"]

    assert metadata["detected_format"] == "markdown"
    assert isinstance(metadata.get("processing_date"), str)
    assert len(chapters) >= 1
    assert toc_html is not None
    assert 'href="#chapter_1"' in toc_html
    assert "body" in result["css"].lower()
