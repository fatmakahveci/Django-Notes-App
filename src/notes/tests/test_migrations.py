"""Renaming Python packages must not create a second set of database tables."""

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from ..models import Post


class ExistingDatabaseCompatibilityTests(TransactionTestCase):
    def test_legacy_database_is_upgraded_in_place_by_the_renamed_app(self):
        old = [("blog_app", "0012_post_publication_status")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            user = apps.get_model("auth", "User").objects.create(username="existing-notes-owner")
            author = apps.get_model("blog_app", "Author").objects.create(user=user, user_name="Writer")
            original = apps.get_model("blog_app", "Post").objects.create(
                author=author, title="Existing draft", content="Original text",
                search_text="existing draft original text", is_published=False,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            upgraded = Post.objects.get(pk=original.pk)
            self.assertEqual(upgraded.content, "Original text")
            self.assertFalse(upgraded.is_published)
            self.assertEqual(upgraded.author.user_id, user.pk)
            self.assertIsNone(upgraded.deleted_at)
            self.assertFalse(upgraded.is_pinned)
            self.assertEqual(ContentType.objects.get_for_model(Post).app_label, "blog_app")
            tables = connection.introspection.table_names()
            self.assertIn("blog_app_post", tables)
            self.assertNotIn("notes_post", tables)
        finally:
            MigrationExecutor(connection).migrate(latest)
