from django.contrib.auth.models import User
from django.db import models

from tinymce import models as tinymce_models


class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_name = models.CharField(max_length=20, default="user")

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
    categories = models.ManyToManyField(Category)
    publish_time = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-publish_time']

    def __str__(self):
        return self.title
