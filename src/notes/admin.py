from django.contrib import admin

from .models import Author, Category, Post, NoteRecovery
from .notebook import remember


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_published", "publish_time")
    list_filter = ("is_published", "categories")
    list_select_related = ("author",)
    search_fields = ("title", "content")
    exclude = ("tags",)

    def save_model(self, request, obj, form, change):
        if change:
            remember(Post.objects.get(pk=obj.pk))
            obj.version += 1
            NoteRecovery.objects.filter(user=obj.author.user, key=str(obj.pk)).delete()
        super().save_model(request, obj, form, change)


admin.site.register(Author)
admin.site.register(Category)
