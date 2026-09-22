from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import AuthAttempt, Author, Category, Post


class NoteFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner")
        cls.other = User.objects.create_user("other")
        cls.author = Author.objects.create(user=cls.owner, user_name="Owner")
        cls.other_author = Author.objects.create(user=cls.other, user_name="Other")
        cls.category = Category.objects.create(title="Engineering")
        cls.second_category = Category.objects.create(title="Travel")
        cls.post = Post.objects.create(title="Django journal", content="<p>Database migrations</p>", author=cls.author)
        cls.post.categories.add(cls.category)
        cls.other_post = Post.objects.create(title="Holiday", content="<p>Coastal walks</p>", author=cls.other_author)
        cls.other_post.categories.add(cls.second_category)

    def test_public_detail_shows_full_content_and_preview_is_bounded(self):
        self.post.content = "<p>" + "word " * 300 + "last sentence</p>"
        self.post.save()
        feed = self.client.get(reverse("home"))
        self.assertNotContains(feed, "last sentence")
        self.assertContains(feed, reverse("post-detail", args=[self.post.pk]))
        detail = self.client.get(reverse("post-detail", args=[self.post.pk]))
        self.assertContains(detail, "last sentence")
        self.assertNotContains(detail, "Edit note")
        self.assertNotContains(detail, "Delete note")

    def test_detail_escapes_untrusted_html(self):
        self.post.content = '<p>&lt;img src=x onerror=alert(1)&gt;</p><script>bad()</script>'
        self.post.save()
        response = self.client.get(reverse("post-detail", args=[self.post.pk]))
        self.assertContains(response, "&lt;img src=x onerror=alert(1)&gt;")
        self.assertNotContains(response, "<img")
        self.assertNotContains(response, "bad()")

    def test_owner_can_edit_content_categories_but_not_author(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("post-edit", args=[self.post.pk]), {
            "title": "Updated note", "content": "<p>Updated content</p>",
            "categories": [self.second_category.pk], "author": self.other_author.pk,
        })
        self.assertRedirects(response, reverse("post-detail", args=[self.post.pk]))
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Updated note")
        self.assertEqual(self.post.content, "<p>Updated content</p>")
        self.assertEqual(self.post.author, self.author)
        self.assertEqual(list(self.post.categories.all()), [self.second_category])
        response = self.client.get(reverse("post-detail", args=[self.post.pk]))
        self.assertContains(response, "Edit note")
        self.assertContains(response, "Delete note")

    def test_owner_can_remove_all_categories(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("post-edit", args=[self.post.pk]), {
            "title": self.post.title, "content": self.post.content,
        })
        self.assertRedirects(response, reverse("post-detail", args=[self.post.pk]))
        self.assertFalse(self.post.categories.exists())

    def test_invalid_edit_preserves_original_post(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("post-edit", args=[self.post.pk]), {
            "title": "Changed", "content": "<p>&nbsp;</p>",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("content", response.context["form"].errors)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Django journal")
        self.assertEqual(self.post.content, "<p>Database migrations</p>")
        self.assertEqual(list(self.post.categories.all()), [self.category])

    def test_delete_requires_confirmation_post(self):
        self.client.force_login(self.owner)
        url = reverse("post-delete", args=[self.post.pk])
        self.assertContains(self.client.get(url), "Delete permanently")
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("my-notes"))
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())
        self.assertTrue(Post.objects.filter(pk=self.other_post.pk).exists())

    def test_other_user_cannot_edit_or_delete_even_with_direct_requests(self):
        self.client.force_login(self.other)
        for action in ("post-edit", "post-delete"):
            for method in (self.client.get, self.client.post):
                with self.subTest(action=action, method=method):
                    response = method(reverse(action, args=[self.post.pk]), {
                        "title": "Forged", "content": "Forged", "author": self.other_author.pk,
                    })
                    self.assertEqual(response.status_code, 404)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Django journal")
        self.assertEqual(self.post.author, self.author)

    def test_anonymous_users_cannot_edit_delete_or_view_my_notes(self):
        for url in [reverse("post-edit", args=[self.post.pk]),
                    reverse("post-delete", args=[self.post.pk]), reverse("my-notes")]:
            for method in (self.client.get, self.client.post):
                response = method(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(parse_qs(urlsplit(response.url).query)["next"], [url])
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_edit_and_delete_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for action in ("post-edit", "post-delete"):
            self.assertEqual(client.post(reverse(action, args=[self.post.pk]), {}).status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_unsupported_methods_and_missing_posts(self):
        self.client.force_login(self.owner)
        for action in ("post-edit", "post-delete"):
            url = reverse(action, args=[self.post.pk])
            self.assertEqual(self.client.put(url).status_code, 405)
        for action in ("post-detail", "post-edit", "post-delete"):
            self.assertEqual(self.client.get(reverse(action, args=[999999])).status_code, 404)

    def test_search_matches_title_and_content(self):
        for query in ("django", "MIGRATIONS"):
            response = self.client.get(reverse("home"), {"q": query})
            self.assertEqual(list(response.context["posts"]), [self.post])
        response = self.client.get(reverse("home"), {"q": "not-found"})
        self.assertContains(response, "No notes match your filters")
        self.assertEqual(list(response.context["posts"]), [])

    def test_search_uses_visible_text_entities_and_unicode(self):
        self.post.title = "Formatting"
        self.post.content = '<p>Planning &amp; <strong>ideas</strong></p><p>CAFÉ notes</p><script>secretcode</script>'
        self.post.save()
        for query in ("Planning & ideas", "café", "ideas   café"):
            response = self.client.get(reverse("home"), {"q": query})
            self.assertEqual(list(response.context["posts"]), [self.post])
        for hidden in ("strong", "amp;", "secretcode"):
            response = self.client.get(reverse("home"), {"q": hidden})
            self.assertEqual(list(response.context["posts"]), [])

    def test_search_document_updates_after_edit_and_partial_save(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("post-edit", args=[self.post.pk]), {
            "title": "Replacement title", "content": "<p>Replacement <em>text</em></p>",
        })
        self.assertEqual(list(self.client.get(reverse("home"), {"q": "Database migrations"}).context["posts"]), [])
        self.assertEqual(list(self.client.get(reverse("home"), {"q": "Replacement text"}).context["posts"]), [self.post])
        self.post.refresh_from_db()
        self.post.content = "<p>Partially saved</p>"
        self.post.save(update_fields=["content"])
        self.assertEqual(list(self.client.get(reverse("home"), {"q": "Partially saved"}).context["posts"]), [self.post])

    def test_category_and_search_filters_combine(self):
        response = self.client.get(reverse("home"), {"category": self.category.pk})
        self.assertEqual(list(response.context["posts"]), [self.post])
        response = self.client.get(reverse("home"), {"category": self.category.pk, "q": "Holiday"})
        self.assertEqual(list(response.context["posts"]), [])
        for invalid in ("not-a-number", "9" * 100, "999999", "-1"):
            response = self.client.get(reverse("home"), {"category": invalid})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context["posts"]), [])

    def test_my_notes_remains_scoped_when_filters_are_supplied(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("my-notes"))
        self.assertEqual(list(response.context["posts"]), [self.post])
        for filters in ({"q": "Holiday"}, {"category": self.second_category.pk}, {"user": self.other.pk}):
            response = self.client.get(reverse("my-notes"), filters)
            self.assertNotIn(self.other_post, list(response.context["posts"]))

    def test_filters_survive_pagination_and_are_escaped(self):
        for i in range(11):
            post = Post.objects.create(title=f"A & B {i}", content="Text", author=self.author)
            post.categories.add(self.category)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("my-notes"), {"q": "A & B", "category": self.category.pk})
        self.assertContains(response, f'?page=2&amp;q=A+%26+B&amp;category={self.category.pk}')
        second = self.client.get(reverse("my-notes"), {"q": "A & B", "category": self.category.pk, "page": 2})
        self.assertEqual(len(second.context["posts"]), 1)
        malicious = self.client.get(reverse("home"), {"q": '"><script>alert(1)</script>'})
        self.assertNotContains(malicious, "<script>alert(1)</script>")

    def test_short_visible_text_is_valid(self):
        self.client.force_login(self.owner)
        for content in ("b", "0", "u", "<p>Hello 👩‍💻</p>"):
            response = self.client.post(reverse("post-form"), {"title": "Short", "content": content})
            self.assertRedirects(response, reverse("home"))


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    AUTH_ATTEMPT_LIMITS={"login": [("ip", 3, 600), ("username", 2, 600)], "signup": [("ip", 2, 3600)]},
)
class AuthenticationThrottleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("writer", password="correct-password")
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.clock = patch("blog_app.middleware.timezone.now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_login_limit_blocks_even_correct_password_then_expires(self):
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("login"), {"username": "writer", "password": "wrong"}).status_code, 200)
        response = self.client.post(reverse("login"), {"username": "writer", "password": "correct-password"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "600")
        self.assertNotIn("_auth_user_id", self.client.session)
        with patch("blog_app.middleware.timezone.now", return_value=self.now + timedelta(seconds=601)):
            response = self.client.post(reverse("login"), {"username": "writer", "password": "correct-password"})
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(AuthAttempt.objects.filter(expires_at__lte=self.now + timedelta(seconds=601)).exists())

    def test_ip_limit_cannot_be_bypassed_by_changing_usernames_or_forwarded_headers(self):
        for i in range(3):
            response = self.client.post(reverse("login"), {"username": f"unknown-{i}", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("login"), {"username": "new", "password": "wrong"}, HTTP_X_FORWARDED_FOR="203.0.113.99")
        self.assertEqual(response.status_code, 429)

    def test_username_limit_applies_across_ip_addresses(self):
        for ip in ("192.0.2.1", "192.0.2.2"):
            self.client.post(reverse("login"), {"username": "writer", "password": "wrong"}, REMOTE_ADDR=ip)
        response = self.client.post(reverse("login"), {"username": "writer", "password": "wrong"}, REMOTE_ADDR="192.0.2.3")
        self.assertEqual(response.status_code, 429)

    def test_admin_login_shares_the_public_login_limit(self):
        for _ in range(2):
            self.client.post(reverse("login"), {"username": "writer", "password": "wrong"})
        response = self.client.post(reverse("admin:login"), {"username": "writer", "password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_signup_is_limited_without_creating_account(self):
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("signup"), {}).status_code, 200)
        response = self.client.post(reverse("signup"), {
            "username": "new-writer", "password1": "Unique-phrase-284!", "password2": "Unique-phrase-284!",
        })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "3600")
        self.assertFalse(User.objects.filter(username="new-writer").exists())
        with patch("blog_app.middleware.timezone.now", return_value=self.now + timedelta(hours=1)):
            self.assertEqual(self.client.post(reverse("signup"), {}).status_code, 200)

    def test_get_and_csrf_rejected_requests_do_not_consume_quota(self):
        for _ in range(4):
            self.assertEqual(self.client.get(reverse("login")).status_code, 200)
            self.assertEqual(self.client.get(reverse("signup")).status_code, 200)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("login"), {}).status_code, 403)
        self.assertEqual(client.post(reverse("signup"), {}).status_code, 403)
        self.assertFalse(AuthAttempt.objects.exists())

    def test_counters_are_shared_between_clients_and_hide_identifiers(self):
        for client in (Client(), Client()):
            client.post(reverse("login"), {"username": "writer", "password": "wrong"})
        self.assertEqual(Client().post(reverse("login"), {"username": "writer", "password": "wrong"}).status_code, 429)
        for key in AuthAttempt.objects.values_list("key", flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn("writer", key)
            self.assertNotIn("127.0.0.1", key)


class SearchMigrationTests(TransactionTestCase):
    def test_existing_notes_receive_searchable_text_without_content_changes(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        old = [("blog_app", "0010_authattempt")]
        new = [("blog_app", "0011_post_search_text")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            user = apps.get_model("auth", "User").objects.create(username="existing")
            author = apps.get_model("blog_app", "Author").objects.create(user=user, user_name="Existing")
            content = "<p>Planning &amp; <strong>ideas</strong></p>"
            post = apps.get_model("blog_app", "Post").objects.create(title="Existing note", content=content, author=author)
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            migrated = executor.loader.project_state(new).apps.get_model("blog_app", "Post").objects.get(pk=post.pk)
            self.assertEqual(migrated.search_text, "existing note planning & ideas")
            self.assertEqual(migrated.content, content)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
