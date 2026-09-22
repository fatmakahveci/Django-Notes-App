import unicodedata

import nh3
from django import template
from django.utils.html import format_html, format_html_join
from django.template.defaultfilters import linebreaks_filter

from django.utils.safestring import mark_safe
from notes.text import normalize_search, plain_text, safe_html

register = template.Library()
# Keep autoescaping enabled: decoded entities can contain literal HTML characters.
register.filter("note_text", plain_text)


@register.filter
def formatted_note(value):
    cleaned = mark_safe(safe_html(value))
    # Plain textarea notes still need their original paragraph boundaries.
    return cleaned if nh3.is_html(value) else linebreaks_filter(cleaned)


@register.filter
def highlight(value, query):
    """Map normalized matches back to original text, then escape every segment."""
    value, query = str(value), normalize_search(str(query))
    if not query:
        return value
    normalized, positions = [], []
    index = 0
    while index < len(value):
        end = index + 1
        while end < len(value) and unicodedata.combining(value[end]):
            end += 1
        for char in unicodedata.normalize("NFKC", value[index:end]).casefold():
            if char.isspace():
                if not normalized or normalized[-1] == " ":
                    continue
                char = " "
            normalized.append(char)
            positions.append((index, end))
        index = end
    document = "".join(normalized)
    pieces, cursor, search_from = [], 0, 0
    while (match := document.find(query, search_from)) >= 0:
        start, end = positions[match][0], positions[match + len(query) - 1][1]
        if start >= cursor:
            pieces.extend([value[cursor:start], format_html("<mark>{}</mark>", value[start:end])])
            cursor = end
        search_from = match + len(query)
    pieces.append(value[cursor:])
    return format_html_join("", "{}", ((piece,) for piece in pieces))
