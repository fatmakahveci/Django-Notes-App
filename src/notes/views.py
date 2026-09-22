import json

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .forms import PostForm, SignupForm, tag_names, SearchFilters
from .models import Author, Category, Post, NoteRecovery, Tag
from .notebook import remember
from .transfer import markdown_title, markdown_note, export_notes, import_notes
from .text import normalize_search, plain_text


SORT_OPTIONS = {
    "newest": ("Newest first", ("-publish_time", "-pk")),
    "oldest": ("Oldest first", ("publish_time", "pk")),
    "title": ("Title A–Z", (Lower("title"), "pk")),
}


def _post_list(request, *, mine=False):
    # Search text is needed for filtering, but need not be loaded for rendering.
    posts = Post.objects.filter(deleted_at__isnull=True).select_related("author").prefetch_related("categories").defer("search_text")
    if mine:
        posts = posts.filter(author__user=request.user).prefetch_related("tags")
    else:
        posts = posts.filter(is_published=True)
    state = request.GET.get("state", "all") if mine else "all"
    if state not in {"all", "published", "draft"}:
        state = "all"
    if state != "all":
        posts = posts.filter(is_published=state == "published")
    sort = request.GET.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("category", "")
    if query:
        posts = posts.filter(search_text__contains=normalize_search(query))
    if category:
        # Bound numeric input before conversion to avoid database integer overflow.
        if category.isascii() and category.isdigit() and len(category) <= 18:
            posts = posts.filter(categories__pk=int(category))
        else:
            posts = posts.none()
    date_filters = SearchFilters(request.GET)
    if date_filters.is_valid():
        for name, lookup in (("after", "publish_time__date__gte"), ("before", "publish_time__date__lte")):
            if date_filters.cleaned_data[name]:
                posts = posts.filter(**{lookup: date_filters.cleaned_data[name]})
    else:
        posts = posts.none()
    tag = request.GET.get("tag", "") if mine else ""
    if tag:
        if tag.isascii() and tag.isdigit() and len(tag) <= 18:
            posts = posts.filter(tags__pk=int(tag), tags__owner=request.user)
        else:
            posts = posts.none()
    # The primary key breaks timestamp ties so pagination has a stable order.
    page = Paginator(posts.order_by(*(["-is_pinned"] if mine else []), *SORT_OPTIONS[sort][1]), 10).get_page(request.GET.get("page"))
    filters = {key: value for key, value in {"q": query, "category": category, "tag": tag, "after": request.GET.get("after", ""), "before": request.GET.get("before", "")}.items() if value}
    if sort != "newest":
        filters["sort"] = sort
    if state != "all":
        filters["state"] = state
    return render(request, "notes/list.html", {
        "posts": page, "page_obj": page, "query": query, "selected_category": category,
        "categories": Category.objects.order_by("title", "pk"), "mine": mine,
        "sort": sort, "sort_label": SORT_OPTIONS[sort][0], "state": state,
        "sort_options": [(key, value[0]) for key, value in SORT_OPTIONS.items()],
        "pagination_query": urlencode(filters), "date_filters": date_filters,
        "selected_tag": tag, "tags": Tag.objects.filter(owner=request.user) if mine else [],
        "advanced_active": bool(tag or request.GET.get("after") or request.GET.get("before")),
    })


def home(request):
    return _post_list(request)


@login_required
@never_cache
def my_notes(request):
    return _post_list(request, mine=True)


def _readable_posts(request):
    visible = Q(is_published=True)
    if request.user.is_authenticated:
        visible |= Q(author__user=request.user)
    return Post.objects.filter(visible, deleted_at__isnull=True).defer("search_text")


@require_safe
@never_cache
def post_detail(request, pk):
    post = get_object_or_404(_readable_posts(request).select_related("author").prefetch_related("categories"), pk=pk)
    return render(request, "notes/detail.html", {"post": post, "note_text": plain_text(post.content)})


@require_safe
def download_post(request, pk):
    post = get_object_or_404(_readable_posts(request), pk=pk)
    markdown = request.GET.get("format") == "md"
    text = f"# {markdown_title(post.title)}\n\n{markdown_note(post)}" if markdown else f"{post.title}\n\n{plain_text(post.content)}\n"
    response = HttpResponse(text, content_type="text/markdown; charset=utf-8" if markdown else "text/plain; charset=utf-8")
    # Use a generated filename rather than putting user-provided titles in headers.
    response["Content-Disposition"] = f'attachment; filename="note-{post.pk}.{"md" if markdown else "txt"}"'
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(request, "Your account has been created.")
        return redirect("home")
    return render(request, "accounts/signup.html", {"form": form})


def about(request):
    return render(request, "about.html")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def create_post(request):
    recovery = _recovery(request, "new")
    form = PostForm(request.POST if request.method == "POST" else None, initial=recovery.data)
    _check_recovery(request, form, recovery)
    if request.method == "POST" and form.is_valid():
        # Save the author, note, and category links together or roll them all back.
        with transaction.atomic():
            author, _ = Author.objects.get_or_create(
                user=request.user, defaults={"user_name": request.user.get_username()},
            )
            post = form.save(commit=False)
            post.author = author
            post.save()
            form.save_m2m()
            if recovery.pk:
                recovery.delete()
        messages.success(request, "Your note has been published." if post.is_published else "Your draft has been saved.")
        return redirect("home" if post.is_published else "my-notes")
    return render(request, "notes/form.html", {"form": form, "recovery": recovery, "note_version": 0, "recovery_version": request.POST.get("recovery_version", recovery.version)})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def edit_post(request, pk):
    # Scope the lookup itself: hiding edit controls does not protect direct requests.
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk, author__user=request.user, deleted_at__isnull=True)
    recovery = _recovery(request, str(post.pk))
    form = PostForm(request.POST if request.method == "POST" else None, instance=post, initial=recovery.data)
    _check_recovery(request, form, recovery)
    if request.method == "POST" and request.POST.get("note_version", str(post.version)) != str(post.version):
        form.add_error(None, "This note changed in another tab. Copy your text, then reload before saving.")
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            remember(Post.objects.get(pk=post.pk))
            post.version += 1
            form.save()
            if recovery.pk:
                recovery.delete()
        messages.success(request, "Your note has been updated.")
        return redirect("post-detail", pk=post.pk)
    return render(request, "notes/form.html", {"form": form, "post": post, "recovery": recovery, "note_version": request.POST.get("note_version", post.version), "recovery_version": request.POST.get("recovery_version", recovery.version)})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def delete_post(request, pk):
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk, author__user=request.user, deleted_at__isnull=True)
    # GET only shows confirmation; deletion requires a CSRF-protected POST.
    if request.method == "POST":
        post.deleted_at = timezone.now()
        post.version += 1
        post.save(update_fields=["deleted_at", "version"])
        NoteRecovery.objects.filter(user=request.user, key=str(pk)).delete()
        messages.success(request, "Your note has been moved to Trash.")
        return redirect("my-notes")
    return render(request, "notes/confirm_delete.html", {"post": post})


def _check_recovery(request, form, recovery):
    if request.method == "POST" and request.POST.get("recovery_version", str(recovery.version)) != str(recovery.version):
        form.add_error(None, "Another tab changed the recovery copy. Copy your text, then reload before saving.")


def _input_id(value):
    return int(value) if value.isascii() and value.isdigit() and len(value) <= 18 else 0


def _recovery(request, key):
    return NoteRecovery.objects.select_for_update().filter(user=request.user, key=key).first() or NoteRecovery(user=request.user, key=key)


@login_required
@never_cache
@require_http_methods(["POST"])
@transaction.atomic
def autosave(request, pk=None):
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk, author__user=request.user, deleted_at__isnull=True) if pk else None
    try:
        payload = json.loads(request.body)
        data = payload["data"]
        version = int(payload["version"])
        if not isinstance(data, dict) or version < 0:
            raise ValueError
        if post and str(payload.get("note_version")) != str(post.version):
            return JsonResponse({"error": "This note changed. Reload before continuing."}, status=409)
        title, content = data.get("title", ""), data.get("content", "")
        categories = data.get("categories", [])
        if not isinstance(title, str) or not isinstance(content, str) or len(title) > 100 or len(content.encode("utf-8")) > 200_000:
            raise ValueError
        if not isinstance(categories, list) or len(categories) > 100:
            raise ValueError
        categories = list(Category.objects.filter(pk__in=[int(c) for c in categories]).values_list("pk", flat=True))
        data = {"title": title, "content": content, "categories": categories,
                "visibility": "draft", "personal_tags": data.get("personal_tags", "")}
        if not isinstance(data["personal_tags"], str) or len(data["personal_tags"]) > 400:
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return JsonResponse({"error": "The recovery copy could not be saved. Check the note size."}, status=400)
    key = str(pk) if pk else "new"
    with transaction.atomic():
        recovery, _ = NoteRecovery.objects.get_or_create(user=request.user, key=key)
        if version == 0 and recovery.version == 0 and not data["title"].strip() and not plain_text(data["content"]).strip():
            return JsonResponse({"version": 0})
        # Compare-and-swap prevents a second tab from overwriting a newer recovery.
        changed = NoteRecovery.objects.filter(pk=recovery.pk, version=version).update(
            data=data, version=version + 1, updated_at=timezone.now(),
        )
        if not changed:
            return JsonResponse({"error": "Another tab saved a newer recovery copy. Reload before continuing."}, status=409)
    return JsonResponse({"version": version + 1})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def trash(request):
    posts = Post.objects.select_for_update().filter(author__user=request.user, deleted_at__isnull=False)
    if request.method == "POST":
        post = get_object_or_404(posts, pk=_input_id(request.POST.get("note", "")))
        action = request.POST.get("action")
        if action == "restore":
            post.deleted_at = None
            post.is_published = False
            post.version += 1
            post.save(update_fields=["deleted_at", "is_published", "version"])
            messages.success(request, "Your note has been restored as a private draft.")
        elif action == "purge" and request.POST.get("confirm") == "yes":
            NoteRecovery.objects.filter(user=request.user, key=str(post.pk)).delete()
            post.delete()
            messages.success(request, "Your note has been permanently deleted.")
        else:
            messages.error(request, "Confirm permanent deletion or choose Restore.")
        return redirect("trash")
    return render(request, "notes/trash.html", {"posts": Paginator(posts.order_by("-deleted_at", "-pk"), 10).get_page(request.GET.get("page"))})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def history(request, pk):
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk, author__user=request.user, deleted_at__isnull=True)
    if request.method == "POST":
        revision = get_object_or_404(post.revisions, pk=_input_id(request.POST.get("revision", "")))
        if request.POST.get("note_version") != str(post.version):
            messages.error(request, "The note changed. Review its latest version before restoring.")
            return redirect("post-history", pk=pk)
        remember(post)
        post.title, post.content = revision.data["title"], revision.data["content"]
        post.is_published = False
        post.version += 1
        post.save()
        post.categories.set(Category.objects.filter(pk__in=revision.data.get("categories", [])))
        post.tags.set(Tag.objects.filter(owner=request.user, pk__in=revision.data.get("tags", [])))
        NoteRecovery.objects.filter(user=request.user, key=str(pk)).delete()
        messages.success(request, "The version has been restored as a private draft. Your previous text is in history.")
        return redirect("post-detail", pk=pk)
    return render(request, "notes/history.html", {"post": post, "revisions": Paginator(post.revisions.all(), 10).get_page(request.GET.get("page"))})


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def pin_note(request, pk):
    post = get_object_or_404(Post.objects.select_for_update(), pk=pk, author__user=request.user, deleted_at__isnull=True)
    post.is_pinned = request.POST.get("pinned") == "yes"
    post.save(update_fields=["is_pinned"])
    return redirect("my-notes")


@login_required
@never_cache
@require_http_methods(["POST"])
@transaction.atomic
def bulk_notes(request):
    ids = request.POST.getlist("notes")
    action = request.POST.get("action")
    if not ids or len(ids) > 100 or any(not value.isascii() or not value.isdigit() or len(value) > 18 for value in ids):
        messages.error(request, "Select between 1 and 100 notes.")
        return redirect("my-notes")
    posts = list(Post.objects.select_for_update().filter(pk__in=ids, author__user=request.user, deleted_at__isnull=True))
    if len(posts) != len(set(ids)):
        return HttpResponse("One or more notes are unavailable. Nothing was changed.", status=404)
    if action not in {"publish", "draft", "trash", "tag"}:
        return HttpResponse("Choose a valid action.", status=400)
    if action in {"publish", "trash"} and request.POST.get("confirm") != "yes":
        return render(request, "notes/bulk_confirm.html", {"posts": posts, "action": action})
    tags = []
    if action == "tag":
        try:
            names = tag_names(request.POST.get("personal_tags", "")[:401])
            if not names:
                raise ValidationError("Enter at least one tag.")
            for post in posts:
                if len(set(post.tags.values_list("name", flat=True)) | set(names)) > 12:
                    raise ValidationError("A note can have at most 12 tags. Nothing was changed.")
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("my-notes")
        tags = [Tag.objects.get_or_create(owner=request.user, name=name)[0] for name in names]
    for post in posts:
        remember(post)
        if action == "trash":
            post.deleted_at = timezone.now()
        elif action in {"publish", "draft"}:
            post.is_published = action == "publish"
        else:
            post.tags.add(*tags)
        post.version += 1
        post.save()
        # A stale recovery must never silently undo a deliberate collection action.
        NoteRecovery.objects.filter(user=request.user, key=str(post.pk)).delete()
    messages.success(request, f"Updated {len(posts)} notes.")
    return redirect("my-notes")


@login_required
@never_cache
@require_safe
def export_collection(request):
    posts = Post.objects.filter(author__user=request.user).prefetch_related("tags", "categories")
    try:
        archive = export_notes(posts)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("transfer-notes")
    response = HttpResponse(archive, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="notes-backup.zip"'
    return response


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def transfer_notes(request):
    error = ""
    if request.method == "POST":
        try:
            if "file" not in request.FILES:
                raise ValidationError("Choose a file to import.")
            notes = import_notes(request.FILES["file"])
            with transaction.atomic():
                author, _ = Author.objects.get_or_create(user=request.user, defaults={"user_name": request.user.get_username()})
                for data in notes:
                    post = Post.objects.create(author=author, title=data["title"], content=data["content"], is_published=False, is_pinned=data["pinned"])
                    post.tags.set([Tag.objects.get_or_create(owner=request.user, name=name)[0] for name in tag_names(",".join(data["tags"]))])
                    post.categories.set(Category.objects.filter(title__in=data["categories"]))
            messages.success(request, f"Imported {len(notes)} notes as private drafts.")
            return redirect("my-notes")
        except ValidationError as exc:
            error = exc.messages[0]
    return render(request, "notes/transfer.html", {"error": error})
