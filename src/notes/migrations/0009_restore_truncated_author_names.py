from django.db import migrations


def restore_author_names(apps, schema_editor):
    Author = apps.get_model("blog_app", "Author")
    authors = Author.objects.using(schema_editor.connection.alias)
    for author in authors.select_related("user").iterator():
        username = author.user.username
        # Restore only names matching the old truncation rule; preserve custom names.
        if len(username) > 20 and author.user_name == username[:20]:
            authors.filter(pk=author.pk).update(user_name=username)


class Migration(migrations.Migration):
    dependencies = [
        ("blog_app", "0008_alter_author_user_name_alter_post_categories"),
    ]

    operations = [
        migrations.RunPython(restore_author_names, migrations.RunPython.noop),
    ]
