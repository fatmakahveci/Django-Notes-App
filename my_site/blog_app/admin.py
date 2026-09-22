from django.contrib import admin

from .models import Author, Category, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_published", "publish_time")
    list_filter = ("is_published", "categories")
    list_select_related = ("author",)
    search_fields = ("title", "content")


admin.site.register(Author)
admin.site.register(Category)
