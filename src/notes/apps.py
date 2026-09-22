from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notes"
    # Preserve migration records, table names, permissions, and content types.
    label = "blog_app"
    verbose_name = "Notes"
