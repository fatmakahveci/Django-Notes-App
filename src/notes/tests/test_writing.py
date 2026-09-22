from urllib.parse import parse_qs

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from ..models import Author, Category, Post


class WritingWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("writing-owner")
        cls.other = User.objects.create_user("writing-reader")
        cls.author = Author.objects.create(user=cls.owner, user_name="Writer")
        cls.category = Category.objects.create(title="Ideas")
        cls.public = Post.objects.create(author=cls.author, title="Public note", content="<p>Public content</p>")
        cls.draft = Post.objects.create(author=cls.author, title="Private draft", content="<p>Private contents</p>", is_published=False)
        cls.draft.categories.add(cls.category)

    def test_drafts_are_hidden_from_feed_search_and_category_filters(self):
        for user in (None, self.owner, self.other):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            for params in ({}, {"q": "Private"}, {"category": self.category.pk}, {"state": "draft"}):
                with self.subTest(user=user, params=params):
                    response = self.client.get(reverse("home"), params)
                    self.assertNotIn(self.draft, list(response.context["posts"]))
                    self.assertNotContains(response, "Private draft")

    def test_only_owner_can_read_or_download_draft(self):
        for route in ("post-detail", "post-download"):
            url = reverse(route, args=[self.draft.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.owner)
            response = self.client.get(url)
            self.assertContains(response, "Private contents")
            self.assertIn("no-store", response["Cache-Control"])
            self.client.logout()

    def test_my_notes_filters_drafts_and_published_notes(self):
        self.client.force_login(self.owner)
        for state, expected in (("draft", [self.draft]), ("published", [self.public])):
            response = self.client.get(reverse("my-notes"), {"state": state})
            self.assertEqual(list(response.context["posts"]), expected)
            self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.other)
        self.assertEqual(list(self.client.get(reverse("my-notes"), {"state": "draft"}).context["posts"]), [])

    def test_create_publish_and_unpublish_draft(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("post-form"), {
            "title": "In progress", "content": "<p>First thought</p>", "visibility": "draft",
        })
        self.assertRedirects(response, reverse("my-notes"))
        post = Post.objects.get(title="In progress")
        self.assertFalse(post.is_published)
        url = reverse("post-edit", args=[post.pk])
        self.assertEqual(self.client.get(url).context["form"]["visibility"].value(), "draft")
        for visibility in ("published", "draft"):
            response = self.client.post(url, {
                "title": post.title, "content": post.content, "visibility": visibility,
            })
            self.assertRedirects(response, reverse("post-detail", args=[post.pk]))
            post.refresh_from_db()
            self.assertEqual(post.is_published, visibility == "published")

    def test_missing_visibility_preserves_draft_and_invalid_choice_is_rejected(self):
        self.client.force_login(self.owner)
        url = reverse("post-edit", args=[self.draft.pk])
        self.client.post(url, {"title": self.draft.title, "content": "Updated"})
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_published)
        response = self.client.post(url, {"title": "Invalid", "content": "Updated", "visibility": "unexpected"})
        self.assertIn("visibility", response.context["form"].errors)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, "Private draft")

    def test_download_is_plain_text_with_safe_filename(self):
        self.public.title = 'A "title"\r\nwith Unicode café'
        self.public.content = '<p>One &amp; two</p><script>bad()</script><p>&lt;img src=x&gt;</p>'
        self.public.save()
        url = reverse("post-download", args=[self.public.pk])
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], f'attachment; filename="note-{self.public.pk}.txt"')
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("One & two\n\n<img src=x>", response.content.decode())
        self.assertNotIn("bad()", response.content.decode())
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_copy_payload_cannot_break_out_of_json_script(self):
        self.public.content = '<p>&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;</p>'
        self.public.save()
        response = self.client.get(reverse("post-detail", args=[self.public.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, r"\u003C/script\u003E")

    def test_sorting_is_allowlisted_and_keeps_filters_in_pagination(self):
        for title in ("zebra", "Apple", "banana"):
            Post.objects.create(author=self.author, title=title, content="Text")
        response = self.client.get(reverse("home"), {"sort": "title"})
        self.assertEqual([post.title for post in response.context["posts"]], ["Apple", "banana", "Public note", "zebra"])
        response = self.client.get(reverse("home"), {"sort": "oldest"})
        self.assertEqual(response.context["posts"][0], self.public)
        response = self.client.get(reverse("home"), {"sort": "author__user__password"})
        self.assertEqual(response.context["sort"], "newest")
        for i in range(12):
            post = Post.objects.create(author=self.author, title=f"Draft {i:02}", content="Text", is_published=False)
            post.categories.add(self.category)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("my-notes"), {
            "q": "Draft", "category": self.category.pk, "sort": "oldest", "state": "draft",
        })
        filters = parse_qs(response.context["pagination_query"])
        self.assertEqual(filters, {"q": ["Draft"], "category": [str(self.category.pk)], "sort": ["oldest"], "state": ["draft"]})
        self.assertTrue(response.context["page_obj"].has_next())

    def test_public_feed_query_count_does_not_grow_with_note_count(self):
        for i in range(15):
            post = Post.objects.create(author=self.author, title=f"Note {i}", content="Text")
            post.categories.add(self.category)
        # Count, paginated notes with authors, prefetched categories, filter choices.
        with self.assertNumQueries(4):
            response = self.client.get(reverse("home"))
        self.assertEqual(len(response.context["posts"]), 10)
        for post in response.context["posts"]:
            self.assertIn("search_text", post.get_deferred_fields())


class PublicationMigrationTests(TransactionTestCase):
    def test_existing_notes_remain_published(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        old = [("blog_app", "0011_post_search_text")]
        new = [("blog_app", "0012_post_publication_status")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            user = apps.get_model("auth", "User").objects.create(username="existing-writer")
            author = apps.get_model("blog_app", "Author").objects.create(user=user, user_name="Writer")
            note = apps.get_model("blog_app", "Post").objects.create(
                author=author, title="Existing public note", content="Original content", search_text="existing public note original content",
            )
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            migrated = executor.loader.project_state(new).apps.get_model("blog_app", "Post").objects.get(pk=note.pk)
            self.assertTrue(migrated.is_published)
            self.assertEqual(migrated.content, "Original content")
            self.assertEqual(migrated.search_text, "existing public note original content")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
