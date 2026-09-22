"""Regression coverage for recovery conflicts and private collection mutations."""

import json
from datetime import datetime, timezone

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Author, Category, NoteRecovery, NoteRevision, Post, Tag
from ..notebook import remember


class NotebookFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("edge-writer")
        cls.other = User.objects.create_user("edge-reader")
        cls.author = Author.objects.create(user=cls.owner, user_name="Writer")
        cls.other_author = Author.objects.create(user=cls.other, user_name="Reader")
        cls.note = Post.objects.create(author=cls.author, title="First", content="<p>Original</p>")
        cls.second = Post.objects.create(author=cls.author, title="Second", content="Text", is_published=False)
        cls.foreign = Post.objects.create(author=cls.other_author, title="Foreign", content="Private", is_published=False)

    def setUp(self):
        self.client.force_login(self.owner)

    def autosave(self, *, note=None, version=0, note_version=1, title="Recovery", content="Unfinished"):
        url = reverse("post-autosave", args=[note.pk]) if note else reverse("note-autosave")
        return self.client.post(url, json.dumps({
            "version": version, "note_version": note_version,
            "data": {"title": title, "content": content},
        }), content_type="application/json")

    def edit(self, note, **data):
        return self.client.post(reverse("post-edit", args=[note.pk]), {
            "title": note.title, "content": note.content, "note_version": note.version, **data,
        })


class RecoveryBoundaryTests(NotebookFixture):
    def test_new_note_recovery_is_scoped_to_the_signed_in_account(self):
        response = self.autosave(title="Owner's unfinished note")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.other)
        response = self.client.get(reverse("post-form"))
        self.assertNotContains(response, "Owner's unfinished note")
        self.assertEqual(self.autosave(title="Reader's unfinished note").status_code, 200)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("post-form"))
        self.assertEqual(response.context["form"]["title"].value(), "Owner's unfinished note")
        self.assertEqual(response.context["form"]["visibility"].value(), "draft")
        self.assertEqual(Post.objects.count(), 3)

    def test_losing_tab_cannot_overwrite_the_winning_recovery(self):
        self.assertEqual(self.autosave(note=self.note, title="First tab").status_code, 200)
        self.assertEqual(self.autosave(note=self.note, title="Stale tab").status_code, 409)
        recovery = NoteRecovery.objects.get(user=self.owner, key=str(self.note.pk))
        self.assertEqual(recovery.data["title"], "First tab")
        self.assertEqual(recovery.version, 1)
        response = self.autosave(note=self.note, version=1, title="First tab again")
        self.assertEqual(response.json()["version"], 2)

    def test_saved_note_rejects_old_autosaves_without_recreating_recovery(self):
        self.autosave(note=self.note)
        self.edit(self.note, content="Explicitly saved text", recovery_version=1)
        response = self.autosave(note=self.note, version=1, note_version=1)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(NoteRecovery.objects.filter(key=str(self.note.pk)).exists())
        self.note.refresh_from_db()
        self.assertEqual(self.note.content, "Explicitly saved text")

    def test_invalid_edit_keeps_recovery_version_and_history_unchanged(self):
        self.autosave(note=self.note)
        response = self.edit(self.note, content="<p>&nbsp;</p>", recovery_version=1)
        self.assertIn("content", response.context["form"].errors)
        self.note.refresh_from_db()
        self.assertEqual(self.note.version, 1)
        self.assertEqual(self.note.content, "<p>Original</p>")
        self.assertFalse(self.note.revisions.exists())
        self.assertEqual(NoteRecovery.objects.get(key=str(self.note.pk)).version, 1)

    def test_malformed_autosave_does_not_damage_an_existing_copy(self):
        self.autosave(note=self.note)
        payloads = [
            "not json", "null", "[]", "{}",
            json.dumps({"version": 1, "data": []}),
            json.dumps({"version": -1, "data": {}}),
            json.dumps({"version": 1, "note_version": 1, "data": {"content": ["bad"]}}),
            json.dumps({"version": 1, "note_version": 1, "data": {"categories": ["invalid"]}}),
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(reverse("post-autosave", args=[self.note.pk]), payload, content_type="application/json")
                self.assertEqual(response.status_code, 400)
                recovery = NoteRecovery.objects.get(key=str(self.note.pk))
                self.assertEqual(recovery.version, 1)
                self.assertEqual(recovery.data["content"], "Unfinished")

    def test_utf8_byte_limit_is_enforced_for_recovery_and_explicit_save(self):
        content = "é" * 100_001
        self.assertEqual(self.autosave(note=self.note, content=content).status_code, 400)
        response = self.edit(self.note, content=content)
        self.assertIn("content", response.context["form"].errors)
        self.note.refresh_from_db()
        self.assertEqual(self.note.content, "<p>Original</p>")

    def test_autosave_requires_post_and_authentication(self):
        url = reverse("post-autosave", args=[self.note.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(url, "{}", content_type="application/json").status_code, 302)
        self.assertFalse(NoteRecovery.objects.exists())


class CollectionBoundaryTests(NotebookFixture):
    def test_bulk_publish_requires_confirmation_and_keeps_history(self):
        url = reverse("bulk-notes")
        data = {"notes": [self.second.pk], "action": "publish"}
        self.assertContains(self.client.post(url, data), "Publish selected notes?")
        self.second.refresh_from_db()
        self.assertFalse(self.second.is_published)
        self.assertFalse(self.second.revisions.exists())
        self.assertRedirects(self.client.post(url, {**data, "confirm": "yes"}), reverse("my-notes"))
        self.second.refresh_from_db()
        self.assertTrue(self.second.is_published)
        self.assertFalse(self.second.revisions.get().data["is_published"])
        self.assertEqual(self.second.version, 2)

    def test_bulk_tag_overflow_rolls_back_the_whole_selection(self):
        self.second.tags.set([Tag.objects.create(owner=self.owner, name=f"tag-{index}") for index in range(12)])
        response = self.client.post(reverse("bulk-notes"), {
            "notes": [self.note.pk, self.second.pk], "action": "tag", "personal_tags": "extra",
        }, follow=True)
        self.assertContains(response, "Nothing was changed")
        self.assertFalse(self.note.tags.exists())
        self.assertEqual(self.second.tags.count(), 12)
        self.assertFalse(Tag.objects.filter(name="extra").exists())
        self.assertFalse(NoteRevision.objects.exists())

    def test_bulk_tagging_adds_tags_without_replacing_existing_ones(self):
        self.note.tags.add(Tag.objects.create(owner=self.owner, name="existing"))
        self.client.post(reverse("bulk-notes"), {
            "notes": [self.note.pk, self.second.pk], "action": "tag", "personal_tags": "WORK, work",
        })
        self.assertEqual(set(self.note.tags.values_list("name", flat=True)), {"existing", "work"})
        self.assertEqual(list(self.second.tags.values_list("name", flat=True)), ["work"])
        self.assertEqual(Tag.objects.filter(owner=self.owner, name="work").count(), 1)

    def test_invalid_bulk_selections_do_not_change_notes(self):
        for selection in ([], ["bad"], ["9" * 30], [str(self.note.pk)] * 101, [self.note.pk, self.foreign.pk]):
            with self.subTest(selection=selection):
                self.client.post(reverse("bulk-notes"), {"notes": selection, "action": "trash", "confirm": "yes"})
                self.assertFalse(Post.objects.filter(deleted_at__isnull=False).exists())
                self.assertFalse(NoteRevision.objects.exists())

    def test_trash_removes_recovery_and_purge_cascades_history_only_for_that_note(self):
        remember(self.note)
        remember(self.second)
        self.autosave(note=self.note)
        self.autosave(note=self.second)
        self.client.post(reverse("post-delete", args=[self.note.pk]))
        self.assertFalse(NoteRecovery.objects.filter(key=str(self.note.pk)).exists())
        self.assertTrue(NoteRecovery.objects.filter(key=str(self.second.pk)).exists())
        self.client.post(reverse("trash"), {"note": self.note.pk, "action": "purge", "confirm": "yes"})
        self.assertFalse(NoteRevision.objects.filter(post_id=self.note.pk).exists())
        self.assertTrue(self.second.revisions.exists())
        self.assertTrue(Post.objects.filter(pk=self.second.pk).exists())

    def test_revision_from_another_note_cannot_be_restored(self):
        remember(self.second)
        response = self.client.post(reverse("post-history", args=[self.note.pk]), {
            "revision": self.second.revisions.get().pk, "note_version": self.note.version,
        })
        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, "First")
        self.assertFalse(self.note.revisions.exists())

    def test_restore_recovers_categories_and_personal_tags_as_a_private_draft(self):
        category = Category.objects.create(title="Ideas")
        tag = Tag.objects.create(owner=self.owner, name="original")
        self.note.categories.add(category)
        self.note.tags.add(tag)
        self.edit(self.note, title="Changed", content="Changed", personal_tags="replacement")
        revision = self.note.revisions.get()
        self.client.post(reverse("post-history", args=[self.note.pk]), {"revision": revision.pk, "note_version": 2})
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_published)
        self.assertEqual(self.note.categories.get(), category)
        self.assertEqual(self.note.tags.get(), tag)
        self.assertEqual(self.note.title, "First")
        self.assertEqual(self.note.revisions.first().data["title"], "Changed")

    def test_personal_tag_ids_cannot_reveal_other_users_notes(self):
        tag = Tag.objects.create(owner=self.other, name="private-label")
        self.foreign.tags.add(tag)
        response = self.client.get(reverse("my-notes"), {"tag": tag.pk})
        self.assertEqual(list(response.context["posts"]), [])
        self.assertNotContains(response, "private-label")
        self.assertNotContains(self.client.get(reverse("home"), {"tag": tag.pk}), "Foreign")

    @override_settings(TIME_ZONE="UTC")
    def test_date_filter_includes_both_boundaries_and_rejects_reversed_range(self):
        for note, day in ((self.note, 10), (self.second, 12), (self.foreign, 13)):
            Post.objects.filter(pk=note.pk).update(publish_time=datetime(2026, 1, day, 23, 59, tzinfo=timezone.utc))
        response = self.client.get(reverse("my-notes"), {"after": "2026-01-10", "before": "2026-01-12"})
        self.assertEqual(set(response.context["posts"]), {self.note, self.second})
        response = self.client.get(reverse("my-notes"), {"after": "2026-01-12", "before": "2026-01-10"})
        self.assertTrue(response.context["date_filters"].non_field_errors())
        self.assertEqual(list(response.context["posts"]), [])
