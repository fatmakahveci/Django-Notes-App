"""Bounded Markdown import/export. ZIP members are read, never extracted."""

import io
import json
import re
from html import escape
import zlib
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from markdown_it import MarkdownIt
from markdownify import markdownify

from .text import plain_text, safe_html

MAX_NOTES = 1000
MAX_TOTAL = 25 * 1024 * 1024
MAX_NOTE = 200_000


def markdown_title(title):
    text = escape(" ".join(title.splitlines()), quote=False)
    return re.sub(r"([\\`*_\[\]])", r"\\\1", text)


def markdown_note(post):
    return markdownify(safe_html(post.content), heading_style="ATX", bullets="-").strip() + "\n"


def export_notes(posts):
    buffer = io.BytesIO()
    metadata = {}
    total = 0
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for index, post in enumerate(posts):
            if index >= MAX_NOTES:
                raise ValidationError("Export supports up to 1,000 notes at a time.")
            content = markdown_note(post).encode("utf-8")
            total += len(content)
            if len(content) > MAX_NOTE or total > MAX_TOTAL:
                raise ValidationError("This collection is too large for one archive. Download large notes individually.")
            name = f"note-{post.pk}.md"
            archive.writestr(name, content)
            metadata[name] = {"title": post.title, "tags": list(post.tags.values_list("name", flat=True)),
                              "categories": list(post.categories.values_list("title", flat=True)),
                              "pinned": post.is_pinned, "published": post.is_published,
                              "trashed": post.deleted_at is not None}
        archive.writestr("manifest.json", json.dumps({"format": 1, "notes": metadata}, ensure_ascii=False))
    return buffer.getvalue()


def import_notes(upload):
    if upload.size > MAX_TOTAL:
        raise ValidationError("Choose a file smaller than 25 MB.")
    raw = upload.read(MAX_TOTAL + 1)
    if len(raw) > MAX_TOTAL:
        raise ValidationError("Choose a file smaller than 25 MB.")
    entries, metadata = [], {}
    try:
        if upload.name.lower().endswith(".zip"):
            with ZipFile(io.BytesIO(raw)) as archive:
                files = [item for item in archive.infolist() if not item.is_dir()]
                if len(files) > MAX_NOTES + 1 or sum(item.file_size for item in files) > MAX_TOTAL:
                    raise ValidationError("Use up to 1,000 notes and 25 MB of uncompressed content.")
                if len({item.filename for item in files}) != len(files):
                    raise ValidationError("The archive contains duplicate filenames.")
                for item in files:
                    path = PurePosixPath(item.filename)
                    if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                        raise ValidationError("The archive contains an invalid path.")
                    if item.filename == "manifest.json":
                        if item.file_size > 2_000_000:
                            raise ValidationError("The archive metadata is too large.")
                        manifest = json.loads(archive.read(item).decode("utf-8"))
                        if not isinstance(manifest, dict) or manifest.get("format") != 1 or not isinstance(manifest.get("notes"), dict):
                            raise ValidationError("Unsupported archive metadata.")
                        metadata = manifest["notes"]
                    elif path.suffix.lower() == ".md":
                        if item.file_size > MAX_NOTE:
                            raise ValidationError("Each Markdown note must be at most 200 KB.")
                        entries.append((path, archive.read(item).decode("utf-8-sig")))
                    else:
                        raise ValidationError("The archive may contain only Markdown files and a manifest.json.")
        elif upload.name.lower().endswith(".md"):
            if len(raw) > MAX_NOTE:
                raise ValidationError("Each Markdown note must be at most 200 KB.")
            entries = [(PurePosixPath(upload.name), raw.decode("utf-8-sig"))]
        else:
            raise ValidationError("Choose a UTF-8 .md file or a .zip of Markdown notes.")
    except (BadZipFile, UnicodeError, ValueError, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error) as error:
        raise ValidationError("The file could not be read as a Markdown backup.") from error
    if not entries or len(entries) > MAX_NOTES:
        raise ValidationError("Choose a file containing between 1 and 1,000 Markdown notes.")
    parser = MarkdownIt("commonmark", {"html": False})
    result = []
    for path, source in entries:
        details = metadata.get(str(path), {})
        if not isinstance(details, dict):
            raise ValidationError("Invalid note metadata.")
        title = details.get("title")
        if title is None:
            lines = source.splitlines()
            if lines and lines[0].startswith("# "):
                title = plain_text(parser.renderInline(lines.pop(0)[2:]))
                source = "\n".join(lines)
            else:
                title = path.stem
        if not isinstance(title, str) or not title.strip() or len(title) > 100:
            raise ValidationError("Each note needs a title of 1–100 characters.")
        tags, categories = details.get("tags", []), details.get("categories", [])
        if not isinstance(tags, list) or len(tags) > 12 or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 32 or ',' in tag for tag in tags):
            raise ValidationError("Invalid personal tags in the backup.")
        if not isinstance(categories, list) or len(categories) > 100 or any(not isinstance(c, str) or len(c) > 100 for c in categories):
            raise ValidationError("Invalid categories in the backup.")
        content = safe_html(parser.render(source))
        if not plain_text(content).strip() or len(content.encode("utf-8")) > MAX_NOTE:
            raise ValidationError("Each imported note needs text and must fit within 200 KB after conversion.")
        result.append({"title": title.strip(), "content": content, "tags": tags, "categories": categories,
                       "pinned": details.get("pinned") is True})
    return result
