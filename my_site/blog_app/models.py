from django.contrib.auth.models import User
from django.db import models
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


class Post(models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    content = tinymce_models.HTMLField()
    search_text = models.TextField(default="", blank=True, editable=False)
    categories = models.ManyToManyField(Category, blank=True)
    publish_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-publish_time"]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or {"title", "content", "search_text"}.intersection(update_fields):
            self.search_text = search_document(self.title, self.content)
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"search_text"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class AuthAttempt(models.Model):
    """Shared fixed-window counters; identities are stored as keyed hashes."""

    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
