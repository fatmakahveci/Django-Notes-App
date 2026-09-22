"""Convert editor HTML to ordinary text; callers must still escape the result."""

import re
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
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
