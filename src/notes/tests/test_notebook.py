import json

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from ..models import Author, NoteRecovery, Post


class NotebookImprovementsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('notebook-owner')
        cls.other = User.objects.create_user('notebook-other')
        cls.author = Author.objects.create(user=cls.owner, user_name='Writer')
        cls.post = Post.objects.create(author=cls.author, title='Original', content='<p>Original text</p>')

    def setUp(self):
        self.client.force_login(self.owner)

    def backup(self, version=0, **kwargs):
        return self.client.post(reverse('post-autosave', args=[self.post.pk]),
            json.dumps({'version': version, 'note_version': 1,
                        'data': {'title': 'Unfinished', 'content': 'Private words', **kwargs}}),
            content_type='application/json')

    def test_autosave_is_private_recoverable_and_conflict_checked(self):
        self.assertEqual(self.backup().status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')
        self.assertNotContains(self.client.get(reverse('home')), 'Private words')
        response = self.client.get(reverse('post-edit', args=[self.post.pk]))
        self.assertEqual(response.context['form']['content'].value(), 'Private words')
        self.assertEqual(self.backup().status_code, 409)
        self.assertEqual(self.backup(version=1).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.backup().status_code, 404)

    def test_autosave_requires_csrf_and_rejects_oversized_content(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('note-autosave')).status_code, 403)
        self.assertEqual(self.backup(content='x' * 200001).status_code, 400)

    def test_explicit_save_removes_recovery_and_rejects_stale_editor(self):
        self.backup()
        url = reverse('post-edit', args=[self.post.pk])
        self.client.post(url, {'title': 'Saved', 'content': 'Saved', 'note_version': 1})
        self.assertFalse(NoteRecovery.objects.exists())
        response = self.client.post(url, {'title': 'Stale', 'content': 'Stale', 'note_version': 1})
        self.assertContains(response, 'changed in another tab')
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Saved')

    def test_formatting_survives_but_active_content_does_not(self):
        self.post.content = '<p><strong>Bold</strong></p><ul><li>Item</li></ul><a href="https://example.org">Link</a><a href="javascript:alert(1)">Bad</a><img src=x onerror=alert(1)><script>bad()</script><svg onload=alert(1)></svg>'
        self.post.save()
        response = self.client.get(reverse('post-detail', args=[self.post.pk]))
        for text in ('<strong>Bold</strong>', '<ul><li>Item</li></ul>', 'href="https://example.org"'):
            self.assertContains(response, text)
        body = response.content.decode().split('data-note-body>')[1].split('</div>')[0]
        for text in ('javascript:', 'onerror', '<script', '<img', '<svg', 'bad()'):
            self.assertNotIn(text, body)

    def test_trash_hides_note_and_restore_is_private(self):
        self.client.post(reverse('post-delete', args=[self.post.pk]))
        for route in ('post-detail', 'post-download', 'post-edit', 'post-autosave'):
            response = self.client.post(reverse(route, args=[self.post.pk])) if route == 'post-autosave' else self.client.get(reverse(route, args=[self.post.pk]))
            self.assertEqual(response.status_code, 404)
        self.assertNotContains(self.client.get(reverse('home')), 'Original text')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('trash'), {'note': self.post.pk, 'action': 'restore'}).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse('trash'), {'note': self.post.pk, 'action': 'restore'})
        self.post.refresh_from_db()
        self.assertIsNone(self.post.deleted_at)
        self.assertFalse(self.post.is_published)

    def test_permanent_delete_requires_confirmation(self):
        self.client.post(reverse('post-delete', args=[self.post.pk]))
        self.client.post(reverse('trash'), {'note': self.post.pk, 'action': 'purge'})
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.client.post(reverse('trash'), {'note': self.post.pk, 'action': 'purge', 'confirm': 'yes'})
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_history_is_private_and_restore_preserves_current_version(self):
        self.client.post(reverse('post-edit', args=[self.post.pk]), {'title': 'New', 'content': '<p>New</p>'})
        revision = self.post.revisions.get()
        self.assertEqual(revision.data['title'], 'Original')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('post-history', args=[self.post.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse('post-history', args=[self.post.pk]), {'revision': revision.pk, 'note_version': 2})
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')
        self.assertFalse(self.post.is_published)
        self.assertEqual(self.post.revisions.first().data['title'], 'New')

    def test_pin_affects_only_owners_collection(self):
        newer = Post.objects.create(author=self.author, title='Newer', content='Text')
        url = reverse('post-pin', args=[self.post.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'pinned': 'yes'})
        self.assertEqual(self.client.get(reverse('my-notes')).context['posts'][0], self.post)
        self.assertEqual(self.client.get(reverse('home')).context['posts'][0], newer)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {'pinned': 'no'}).status_code, 404)

    def test_personal_tags_are_normalized_and_never_public(self):
        self.client.post(reverse('post-edit', args=[self.post.pk]), {'title': 'Original', 'content': 'Text', 'personal_tags': 'Work, work, Secret Label'})
        self.assertEqual(list(self.post.tags.values_list('name', flat=True)), ['secret label', 'work'])
        self.assertContains(self.client.get(reverse('my-notes')), '#secret label')
        self.assertNotContains(self.client.get(reverse('home')), '#secret label')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('my-notes')), '#secret label')

    def test_date_tag_search_highlighting_and_invalid_dates(self):
        from django.utils import timezone
        from ..models import Tag
        tag = Tag.objects.create(owner=self.owner, name='travel')
        self.post.tags.add(tag)
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse('my-notes'), {'after': today, 'before': today, 'tag': tag.pk, 'q': 'original'})
        self.assertEqual(list(response.context['posts']), [self.post])
        self.assertContains(response, '<mark>Original</mark>')
        response = self.client.get(reverse('my-notes'), {'after': 'invalid'})
        self.assertTrue(response.context['date_filters'].errors)
        self.assertEqual(len(response.context['posts']), 0)
        from ..templatetags.note_text import highlight
        self.assertNotIn('<script>', highlight('<script>alert(1)</script>', 'alert'))

    def test_bulk_actions_are_atomic_owner_only_and_confirmed(self):
        foreign = Post.objects.create(author=Author.objects.create(user=self.other), title='Other', content='Text')
        url = reverse('bulk-notes')
        response = self.client.post(url, {'notes': [self.post.pk, foreign.pk], 'action': 'draft'})
        self.assertEqual(response.status_code, 404)
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_published)
        response = self.client.post(url, {'notes': [self.post.pk], 'action': 'trash'})
        self.assertContains(response, 'Move selected notes to Trash?')
        self.post.refresh_from_db()
        self.assertIsNone(self.post.deleted_at)
        self.client.post(url, {'notes': [self.post.pk], 'action': 'tag', 'personal_tags': 'project'})
        self.assertEqual(self.post.tags.get().name, 'project')
        self.client.post(url, {'notes': [self.post.pk], 'action': 'trash', 'confirm': 'yes'})
        self.post.refresh_from_db()
        self.assertIsNotNone(self.post.deleted_at)

    def test_markdown_backup_roundtrip_is_private_and_owner_scoped(self):
        import io
        from zipfile import ZipFile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ..models import Tag
        self.post.content = '<p><strong>Keep formatting</strong></p><ul><li>Item</li></ul>'
        self.post.save()
        self.post.tags.add(Tag.objects.create(owner=self.owner, name='work'))
        Post.objects.create(author=Author.objects.create(user=self.other), title='Foreign', content='Foreign secret')
        response = self.client.get(reverse('export-notes'))
        self.assertIn('no-store', response['Cache-Control'])
        with ZipFile(io.BytesIO(response.content)) as archive:
            text = archive.read(f'note-{self.post.pk}.md').decode()
            self.assertIn('**Keep formatting**', text)
            self.assertEqual(len(archive.namelist()), 2)
        self.client.post(reverse('transfer-notes'), {'file': SimpleUploadedFile('backup.zip', response.content)})
        imported = Post.objects.filter(author=self.author).latest('pk')
        self.assertFalse(imported.is_published)
        self.assertIn('<strong>Keep formatting</strong>', imported.content)
        self.assertEqual(imported.tags.get().name, 'work')

    def test_import_is_atomic_and_rejects_bad_archives(self):
        import io
        from zipfile import ZipFile
        from django.core.files.uploadedfile import SimpleUploadedFile
        for entries in ({'../bad.md': '# Bad\nText'}, {'good.md': '# Good\nText', 'bad.md': ''}):
            buffer = io.BytesIO()
            with ZipFile(buffer, 'w') as archive:
                for name, text in entries.items():
                    archive.writestr(name, text)
            response = self.client.post(reverse('transfer-notes'), {'file': SimpleUploadedFile('bad.zip', buffer.getvalue())})
            self.assertTrue(response.context['error'])
            self.assertEqual(Post.objects.count(), 1)
        self.client.post(reverse('transfer-notes'), {'file': SimpleUploadedFile('note.md', b'# Imported\n\n**Bold**\n<script>alert(1)</script>')})
        imported = Post.objects.get(title='Imported')
        self.assertIn('<strong>Bold</strong>', imported.content)
        self.assertNotIn('<script>', imported.content)

    def test_new_editor_renders_and_stale_recovery_cannot_be_submitted(self):
        self.assertContains(self.client.get(reverse('post-form')), 'data-note-editor')
        self.backup()
        response = self.client.post(reverse('post-edit', args=[self.post.pk]), {
            'title': 'Stale', 'content': 'Old text', 'note_version': 1, 'recovery_version': 0,
        })
        self.assertContains(response, 'Another tab changed the recovery copy')
        self.assertContains(response, 'name="recovery_version" value="0"')
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')

    def test_private_tools_require_login_and_mutations_require_csrf(self):
        protected = [('post-history', [self.post.pk]), ('trash', []), ('transfer-notes', []), ('export-notes', [])]
        self.client.logout()
        for name, args in protected:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for name, args in protected[:3] + [('post-pin', [self.post.pk]), ('bulk-notes', [])]:
            self.assertEqual(client.post(reverse(name, args=args)).status_code, 403)

    def test_import_file_limits_and_blank_new_recovery(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(reverse('transfer-notes'), {'file': SimpleUploadedFile('large.md', b'x' * 200001)})
        self.assertTrue(response.context['error'])
        response = self.client.post(reverse('note-autosave'), json.dumps({'version': 0, 'data': {'title': '', 'content': ''}}), content_type='application/json')
        self.assertEqual(response.json()['version'], 0)

    def test_history_retention_and_note_version_conflict(self):
        from ..notebook import remember
        for i in range(55):
            self.post.title = f'Version {i}'
            remember(self.post)
        self.assertEqual(self.post.revisions.count(), 50)
        revision = self.post.revisions.first()
        self.client.post(reverse('post-history', args=[self.post.pk]), {'revision': revision.pk, 'note_version': 0})
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')

    def test_unicode_highlights_and_plain_text_line_breaks(self):
        from ..templatetags.note_text import highlight, formatted_note
        self.assertEqual(str(highlight('Straße', 'STRASSE')), '<mark>Straße</mark>')
        self.assertEqual(str(highlight('Cafe\u0301', 'café')), '<mark>Cafe\u0301</mark>')
        self.assertIn('One<br>Two', str(formatted_note('One\nTwo')))
        self.assertNotIn('<script>', str(formatted_note('&lt;script&gt;alert(1)&lt;/script&gt;')))

    def test_markdown_title_is_exported_as_literal_text(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.post.title = '<script>alert(1)</script> **literal** &amp;'
        self.post.save()
        response = self.client.get(reverse('post-download', args=[self.post.pk]), {'format': 'md'})
        self.assertNotIn(b'<script>', response.content)
        self.client.post(reverse('transfer-notes'), {'file': SimpleUploadedFile('note.md', response.content)})
        imported = Post.objects.latest('pk')
        self.assertEqual(imported.title, self.post.title)
