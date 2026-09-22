from django.contrib.auth.models import User
from django.db import models, router
from tinymce import models as tinymce_models

from .text import search_document


class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_name = models.CharField(max_length=150, default="user")

    def __str__(self):
        return self.user_name


class Category(models.Model):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title


class Tag(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_personal_tag")]

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    content = tinymce_models.HTMLField()
    search_text = models.TextField(default="", blank=True, editable=False)
    categories = models.ManyToManyField(Category, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    publish_time = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-publish_time"]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            # Materialize once: checking a generator would otherwise consume it.
            update_fields = frozenset(update_fields)
            kwargs["update_fields"] = update_fields
        if update_fields is None or {"title", "content", "search_text"}.intersection(update_fields):
            persisted = {}
            if update_fields is not None:
                unchanged_fields = {"title", "content"} - update_fields
                if unchanged_fields:
                    # Excluded fields may have unsaved edits on this instance.
                    # Index their database values rather than those pending edits.
                    database = kwargs.get("using") or router.db_for_write(type(self), instance=self)
                    persisted = (
                        type(self).objects.using(database).filter(pk=self.pk)
                        .values(*unchanged_fields).first()
                    ) or {}
            self.search_text = search_document(
                persisted["title"] if "title" in persisted else self.title,
                persisted["content"] if "content" in persisted else self.content,
            )
            if update_fields is not None:
                # Partial saves must persist the derived search text alongside its source.
                kwargs["update_fields"] = set(update_fields) | {"search_text"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class AuthAttempt(models.Model):
    """Shared fixed-window counters; identities are stored as keyed hashes."""

    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class NoteRecovery(models.Model):
    """One private recovery copy per writer and editor, never part of the feed."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=30)
    data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="unique_editor_recovery")]


class NoteRevision(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="revisions")
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
