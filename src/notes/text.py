"""Convert editor HTML to ordinary text; callers must still escape the result."""

import re
import unicodedata
import nh3
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    block_tags = {
        "address", "article", "blockquote", "div", "dl", "dt", "dd", "h1",
        "h2", "h3", "h4", "h5", "h6", "hr", "li", "ol", "p", "pre",
        "section", "table", "tr", "ul",
    }
    hidden_tags = {"script", "style", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        # Track nested hidden elements so their text never enters previews or search.
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in self.hidden_tags:
            self.hidden.append(tag)
        if self.hidden:
            return
        if tag in self.block_tags:
            self.parts.append("\n\n")
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag in self.block_tags:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    # Collapse spacing without losing the paragraph boundaries added by the parser.
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_search(text):
    # Apply the same Unicode, case, and whitespace rules to saved text and queries.
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def search_document(title, content):
    return normalize_search(f"{title}\n{plain_text(content)}")


def safe_html(content):
    """Allow document formatting, never scripts, embedded media, or inline styles."""
    return nh3.clean(
        content,
        tags={"p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
              "blockquote", "pre", "code", "h2", "h3", "h4", "h5", "h6", "a", "hr"},
        attributes={"a": {"href", "title"}},
        clean_content_tags={"script", "style", "template", "iframe", "svg", "math"},
        url_schemes={"https", "http", "mailto"},
        link_rel="noopener noreferrer nofollow",
    )
