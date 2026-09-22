from django.contrib.auth.models import User
from django.test import TestCase

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
