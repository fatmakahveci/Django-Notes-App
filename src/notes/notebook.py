"""Operations shared by the editor, history, and collection tools."""

from .models import NoteRevision


def remember(post):
    NoteRevision.objects.create(post=post, data={
        "title": post.title, "content": post.content, "is_published": post.is_published,
        "categories": list(post.categories.values_list("pk", flat=True)),
        "tags": list(post.tags.values_list("pk", flat=True)),
    })
    # Bound storage while keeping the most recent fifty explicit saved versions.
    old = list(post.revisions.values_list("pk", flat=True)[50:])
    if old:
        post.revisions.filter(pk__in=old).delete()
