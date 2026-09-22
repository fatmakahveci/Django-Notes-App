from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase

from .models import Author, Category, Post


class BlogModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="writer", password="test-password")
        self.author = Author.objects.create(user=user, user_name="Writer")
        self.category = Category.objects.create(title="Engineering")

    def test_model_string_representations(self):
        post = Post.objects.create(
            title="Test-driven notes",
            author=self.author,
            content="<p>Useful content</p>",
        )
        post.categories.add(self.category)

        self.assertEqual(str(self.author), "Writer")
        self.assertEqual(str(self.category), "Engineering")
        self.assertEqual(str(post), "Test-driven notes")
        self.assertEqual(list(post.categories.all()), [self.category])

    def test_home_lists_saved_posts(self):
        Post.objects.create(
            title="Visible note",
            author=self.author,
            content="<p>Rendered content</p>",
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible note")


class AccountAndPostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("writer", password="test-password")

    def test_signup_creates_and_logs_in_user(self):
        response = self.client.post("/signup.html", {
            "username": "newwriter",
            "password1": "A-unique-passphrase-928!",
            "password2": "A-unique-passphrase-928!",
        })
        self.assertRedirects(response, "/")
        user = User.objects.get(username="newwriter")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_invalid_signup_displays_errors(self):
        response = self.client.post("/signup.html", {"username": "writer"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_login_and_post_only_logout(self):
        response = self.client.post("/login.html", {
            "username": "writer", "password": "test-password",
        })
        self.assertRedirects(response, "/")
        self.assertEqual(self.client.get("/logout.html").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post("/logout.html"), "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_invalid_login_and_external_redirect(self):
        response = self.client.post("/login.html", {
            "username": "writer", "password": "wrong",
        })
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post("/login.html", {
            "username": "writer", "password": "test-password",
            "next": "https://example.com/",
        })
        self.assertRedirects(response, "/")

    def test_anonymous_users_cannot_create_posts(self):
        for method in (self.client.get, self.client.post):
            response = method("/post_form.html")
            self.assertRedirects(response, "/login.html?next=/post_form.html")
        self.assertFalse(Post.objects.exists())

    def test_post_author_cannot_be_forged_and_categories_are_saved(self):
        other = User.objects.create_user("other")
        other_author = Author.objects.create(user=other, user_name="Other")
        category = Category.objects.create(title="Engineering")
        self.client.force_login(self.user)
        response = self.client.post("/post_form.html", {
            "title": "My note", "content": "<p>Hello</p>",
            "author": other_author.pk, "categories": [category.pk],
        })
        self.assertRedirects(response, "/")
        post = Post.objects.get()
        self.assertEqual(post.author.user, self.user)
        self.assertEqual(list(post.categories.all()), [category])

    def test_category_is_optional_and_author_is_reused(self):
        author = Author.objects.create(user=self.user, user_name="Writer")
        self.client.force_login(self.user)
        response = self.client.post("/post_form.html", {
            "title": "Uncategorized", "content": "Hello",
        })
        self.assertRedirects(response, "/")
        self.assertEqual(Post.objects.get().author, author)
        self.assertEqual(Author.objects.count(), 1)

    def test_invalid_post_shows_errors_without_creating_author(self):
        self.client.force_login(self.user)
        response = self.client.post("/post_form.html", {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Post.objects.exists())
        self.assertFalse(Author.objects.exists())

    def test_feed_shows_date_and_does_not_render_untrusted_html(self):
        author = Author.objects.create(user=self.user, user_name="Writer")
        post = Post.objects.create(title="Safe note", author=author,
                                   content='<script>alert(1)</script><p>Hello</p>')
        response = self.client.get("/")
        self.assertContains(response, post.publish_time.strftime("%b %d, %Y"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "Hello")

    def test_forms_require_csrf_tokens(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        for url in ("/login.html", "/signup.html"):
            self.assertEqual(client.post(url, {}).status_code, 403)
        client.force_login(self.user)
        for url in ("/post_form.html", "/logout.html"):
            self.assertEqual(client.post(url, {}).status_code, 403)


class NoteRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reviewer")
        self.author = Author.objects.create(user=self.user, user_name="Reviewer")

    def test_feed_preserves_paragraphs_breaks_and_decodes_entities(self):
        Post.objects.create(
            title="Formatting", author=self.author,
            content="<p>First &amp; second&nbsp;part</p><p>Third<br>Fourth</p>",
        )
        response = self.client.get("/")
        self.assertContains(response, "<p>First &amp; second part</p>", html=True)
        self.assertContains(response, "<p>Third<br>Fourth</p>", html=True)
        self.assertNotContains(response, "&amp;amp;")
        self.assertNotContains(response, "&amp;nbsp;")

    def test_feed_escapes_encoded_html_and_omits_hidden_content(self):
        Post.objects.create(
            title="Untrusted", author=self.author,
            content=('&lt;img src=x onerror=alert(1)&gt;'
                     '<script>alert(2)</script><style>body{display:none}</style>'
                     '<template>Hidden</template><p>Visible</p>'),
        )
        response = self.client.get("/")
        self.assertContains(response, "&lt;img src=x onerror=alert(1)&gt;")
        for hidden in ("<img", "alert(2)", "body{display:none}", "Hidden"):
            self.assertNotContains(response, hidden)
        self.assertContains(response, "Visible")

    def test_empty_editor_markup_is_rejected_without_creating_a_post(self):
        self.client.force_login(self.user)
        for content in ("<p><br></p>", "<p>&nbsp;</p>", "<p>\u200b</p>",
                        "<script>alert(1)</script>", "<!-- comment -->"):
            with self.subTest(content=content):
                response = self.client.post("/post_form.html", {
                    "title": "Empty", "content": content,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn("content", response.context["form"].errors)
        self.assertFalse(Post.objects.exists())

    def test_valid_rich_text_is_stored_unchanged(self):
        self.client.force_login(self.user)
        content = "<p><strong>Hello</strong> &amp; goodbye</p>"
        self.assertRedirects(self.client.post("/post_form.html", {
            "title": "Rich text", "content": content,
        }), "/")
        self.assertEqual(Post.objects.get().content, content)

    def test_admin_can_edit_a_post_without_categories(self):
        from django.contrib import admin
        from django.test import RequestFactory

        post = Post.objects.create(title="Original", content="Text", author=self.author)
        request = RequestFactory().get("/admin/blog_app/post/")
        request.user = User.objects.create_superuser("admin", password="test-password")
        AdminForm = admin.site._registry[Post].get_form(request, obj=post)
        form = AdminForm({"title": "Edited", "content": "Text", "author": self.author.pk},
                         instance=post)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        post.refresh_from_db()
        self.assertEqual(post.title, "Edited")
        self.assertFalse(post.categories.exists())

    def test_long_usernames_remain_distinct(self):
        usernames = ["abcdefghijklmnopqrst_one", "abcdefghijklmnopqrst_two", "x" * 150]
        for username in usernames:
            user = User.objects.create_user(username=username)
            self.client.force_login(user)
            self.assertRedirects(self.client.post("/post_form.html", {
                "title": "Note", "content": "Text",
            }), "/")
            self.assertEqual(str(Author.objects.get(user=user)), username)
        response = self.client.get("/")
        for username in usernames:
            self.assertContains(response, username)

    def test_feed_paginates_with_stable_order_and_invalid_page_fallback(self):
        from django.utils import timezone

        posts = Post.objects.bulk_create([
            Post(title=f"Note {i}", content="Text", author=self.author) for i in range(23)
        ])
        Post.objects.update(publish_time=timezone.now())
        expected = [post.pk for post in reversed(posts)]
        seen = []
        for number, count in ((1, 10), (2, 10), (3, 3)):
            response = self.client.get("/", {"page": number})
            self.assertContains(response, "<article>", count=count)
            seen.extend(post.pk for post in response.context["posts"])
        self.assertEqual(seen, expected)
        for value, expected_page in (("invalid", 1), (999, 3), (0, 3)):
            response = self.client.get("/", {"page": value})
            self.assertEqual(response.context["page_obj"].number, expected_page)
        self.assertContains(self.client.get("/"), '?page=2')
        self.assertContains(self.client.get("/", {"page": 3}), '?page=2')

    def test_empty_feed_has_no_pagination(self):
        response = self.client.get("/")
        self.assertContains(response, "No notes yet")
        self.assertNotContains(response, 'aria-label="Notes pages"')


class AuthorMigrationTests(TransactionTestCase):
    def test_migration_restores_truncated_names_and_preserves_custom_names(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        old = [("blog_app", "0007_alter_post_content")]
        new = [("blog_app", "0009_restore_truncated_author_names")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            UserModel = apps.get_model("auth", "User")
            AuthorModel = apps.get_model("blog_app", "Author")
            user = UserModel.objects.create(username="abcdefghijklmnopqrst_one")
            truncated = AuthorModel.objects.create(user=user, user_name=user.username[:20])
            custom_user = UserModel.objects.create(username="abcdefghijklmnopqrst_two")
            custom = AuthorModel.objects.create(user=custom_user, user_name="Pen name")
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            AuthorModel = apps.get_model("blog_app", "Author")
            self.assertEqual(AuthorModel.objects.get(pk=truncated.pk).user_name, user.username)
            self.assertEqual(AuthorModel.objects.get(pk=custom.pk).user_name, "Pen name")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
