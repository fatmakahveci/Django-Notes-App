from django.contrib import admin

from .models import Author, Category, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "publish_time")
    search_fields = ("title", "content")


admin.site.register(Author)
admin.site.register(Category)
