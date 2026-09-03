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
