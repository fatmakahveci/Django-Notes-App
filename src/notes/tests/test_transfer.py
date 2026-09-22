"""Exercise untrusted uploads and backup restoration through real archives."""

import io
import json
import warnings
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Author, Category, Post, Tag
from ..transfer import import_notes


def archive_upload(entries):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        # Duplicate-member warnings are expected for deliberately malformed input.
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            for name, content in entries:
                archive.writestr(name, content)
    return SimpleUploadedFile("notes.zip", buffer.getvalue(), content_type="application/zip")


class MarkdownValidationTests(SimpleTestCase):
    def test_bom_heading_and_unicode_are_preserved(self):
        notes = import_notes(SimpleUploadedFile("note.md", "\ufeff# Café ☕\n\nA **useful** idea.".encode()))
        self.assertEqual(notes[0]["title"], "Café ☕")
        self.assertIn("<strong>useful</strong>", notes[0]["content"])

    def test_filename_is_used_when_no_heading_exists(self):
        note = import_notes(SimpleUploadedFile("meeting.md", b"A short reminder."))[0]
        self.assertEqual(note["title"], "meeting")
        self.assertIn("A short reminder.", note["content"])

    def test_archive_paths_are_rejected_without_extracting_files(self):
        for name in ("../outside.md", "/absolute.md", "folder/../../outside.md", "folder\\outside.md"):
            with self.subTest(name=name), self.assertRaisesMessage(ValidationError, "invalid path"):
                import_notes(archive_upload([(name, "Text")]))

    def test_duplicate_members_and_unexpected_files_are_rejected(self):
        cases = [
            [("note.md", "First"), ("note.md", "Second")],
            [("note.md", "Text"), ("image.png", b"not an image")],
        ]
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaises(ValidationError):
                import_notes(archive_upload(entries))

    def test_invalid_archive_encoding_and_metadata_fail_cleanly(self):
        uploads = [
            SimpleUploadedFile("broken.zip", b"not a zip file"),
            SimpleUploadedFile("broken.md", b"\xff\xfe"),
            archive_upload([]),
            archive_upload([("note.md", b"\xff")]),
            archive_upload([("note.md", "Text"), ("manifest.json", "not json")]),
            archive_upload([("note.md", "Text"), ("manifest.json", json.dumps({"format": 2, "notes": {}}))]),
            archive_upload([("note.md", "Text"), ("manifest.json", "[]")]),
        ]
        for upload in uploads:
            with self.subTest(name=upload.name), self.assertRaises(ValidationError):
                import_notes(upload)

    def test_invalid_note_metadata_is_rejected(self):
        cases = [
            [], {"title": ""}, {"title": "x" * 101}, {"title": 42},
            {"tags": "not a list"}, {"tags": ["a,b"]}, {"tags": ["x" * 33]},
            {"tags": [str(i) for i in range(13)]}, {"categories": [None]},
            {"categories": "not a list"},
        ]
        for details in cases:
            with self.subTest(details=details), self.assertRaises(ValidationError):
                import_notes(archive_upload([
                    ("note.md", "Text"),
                    ("manifest.json", json.dumps({"format": 1, "notes": {"note.md": details}})),
                ]))

    def test_compressed_upload_is_checked_against_uncompressed_limit(self):
        upload = archive_upload([("large.md", "a" * 4096)])
        self.assertLess(upload.size, 1024)
        # A reduced resource limit exercises the real ZIP size check without a huge fixture.
        with patch("notes.transfer.MAX_TOTAL", 1024), self.assertRaisesMessage(ValidationError, "uncompressed"):
            import_notes(upload)

    def test_archive_member_count_and_per_note_size_are_bounded(self):
        with patch("notes.transfer.MAX_NOTES", 2), self.assertRaises(ValidationError):
            import_notes(archive_upload([(f"{i}.md", "Text") for i in range(3)]))
        with self.assertRaisesMessage(ValidationError, "200 KB"):
            import_notes(archive_upload([("large.md", "a" * 200001)]))

    def test_converted_unicode_content_must_fit_the_byte_limit(self):
        # The source fits; the generated paragraph markup pushes its UTF-8 size over the limit.
        upload = SimpleUploadedFile("unicode.md", ("é" * 99999).encode("utf-8"))
        self.assertLess(upload.size, 200000)
        with self.assertRaisesMessage(ValidationError, "200 KB"):
            import_notes(upload)

    def test_links_and_raw_html_cannot_create_active_content(self):
        upload = SimpleUploadedFile("note.md", b"[bad](javascript:alert(1))\n\n<script>alert(1)</script>\n\n![tracking](https://example.org/image.png)")
        content = import_notes(upload)[0]["content"]
        self.assertNotIn("<script", content)
        self.assertNotIn("<img", content)
        self.assertNotIn('href="javascript:', content)


class BackupTransactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("backup-writer")
        cls.author = Author.objects.create(user=cls.user)
        cls.category = Category.objects.create(title="Ideas")
        cls.post = Post.objects.create(author=cls.author, title="Saved", content="<p>Text</p>", is_pinned=True)
        cls.post.categories.add(cls.category)
        cls.post.tags.add(Tag.objects.create(owner=cls.user, name="original"))

    def setUp(self):
        self.client.force_login(self.user)

    def test_import_rolls_back_notes_authors_and_tags_when_a_later_write_fails_validation(self):
        # NFKC expands each ligature into three characters, exceeding the normalized tag limit.
        upload = archive_upload([
            ("first.md", "First text"), ("second.md", "Second text"),
            ("manifest.json", json.dumps({"format": 1, "notes": {
                "first.md": {"tags": ["new-tag"]},
                "second.md": {"tags": ["ﬃ" * 12]},
            }})),
        ])
        newcomer = User.objects.create_user("new-importer")
        self.client.force_login(newcomer)
        response = self.client.post(reverse("transfer-notes"), {"file": upload})
        self.assertTrue(response.context["error"])
        self.assertFalse(Post.objects.filter(author__user=newcomer).exists())
        self.assertFalse(Author.objects.filter(user=newcomer).exists())
        self.assertFalse(Tag.objects.filter(owner=newcomer).exists())
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_backup_restores_pins_tags_and_existing_categories_but_never_publication(self):
        self.post.deleted_at = timezone.now()
        self.post.save(update_fields=["deleted_at"])
        response = self.client.get(reverse("export-notes"))
        with ZipFile(io.BytesIO(response.content)) as archive:
            metadata = json.loads(archive.read("manifest.json"))["notes"][f"note-{self.post.pk}.md"]
        self.assertTrue(metadata["published"])
        self.assertTrue(metadata["trashed"])
        self.assertTrue(metadata["pinned"])
        self.assertEqual(metadata["categories"], ["Ideas"])
        self.client.post(reverse("transfer-notes"), {"file": SimpleUploadedFile("backup.zip", response.content)})
        restored = Post.objects.latest("pk")
        self.assertNotEqual(restored.pk, self.post.pk)
        self.assertIsNone(restored.deleted_at)
        self.assertFalse(restored.is_published)
        self.assertTrue(restored.is_pinned)
        self.assertEqual(restored.categories.get(), self.category)
        self.assertEqual(restored.tags.get().name, "original")
        self.post.refresh_from_db()
        self.assertIsNotNone(self.post.deleted_at)

    def test_repeated_import_creates_new_drafts_and_does_not_overwrite_existing_notes(self):
        for _ in range(2):
            response = self.client.post(reverse("transfer-notes"), {
                "file": SimpleUploadedFile("note.md", b"# Saved\n\nImported text"),
            })
            self.assertRedirects(response, reverse("my-notes"))
        self.assertEqual(Post.objects.filter(title="Saved", is_published=False).count(), 2)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "<p>Text</p>")
        self.assertTrue(self.post.is_published)

    def test_import_cannot_create_shared_categories_from_metadata(self):
        upload = archive_upload([
            ("note.md", "Text"),
            ("manifest.json", json.dumps({"format": 1, "notes": {
                "note.md": {"categories": ["Ideas", "Unapproved category"]},
            }})),
        ])
        self.client.post(reverse("transfer-notes"), {"file": upload})
        restored = Post.objects.latest("pk")
        self.assertEqual(list(restored.categories.all()), [self.category])
        self.assertFalse(Category.objects.filter(title="Unapproved category").exists())

    def test_export_limit_returns_an_error_instead_of_a_partial_archive(self):
        with patch("notes.transfer.MAX_NOTES", 0):
            response = self.client.get(reverse("export-notes"), follow=True)
        self.assertContains(response, "Export supports up to")
        self.assertNotEqual(response["Content-Type"], "application/zip")
        self.assertEqual(Post.objects.count(), 1)
