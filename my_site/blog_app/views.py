from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .forms import PostForm, SignupForm
from .models import Author, Category, Post
from .text import normalize_search, plain_text


SORT_OPTIONS = {
    "newest": ("Newest first", ("-publish_time", "-pk")),
    "oldest": ("Oldest first", ("publish_time", "pk")),
    "title": ("Title A–Z", (Lower("title"), "pk")),
}


def _post_list(request, *, mine=False):
    # Search text is needed for filtering, but need not be loaded for rendering.
    posts = Post.objects.select_related("author").prefetch_related("categories").defer("search_text")
    if mine:
        posts = posts.filter(author__user=request.user)
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
    # The primary key breaks timestamp ties so pagination has a stable order.
    page = Paginator(posts.order_by(*SORT_OPTIONS[sort][1]), 10).get_page(request.GET.get("page"))
    filters = {key: value for key, value in {"q": query, "category": category}.items() if value}
    if sort != "newest":
        filters["sort"] = sort
    if state != "all":
        filters["state"] = state
    return render(request, "index.html", {
        "posts": page, "page_obj": page, "query": query, "selected_category": category,
        "categories": Category.objects.order_by("title", "pk"), "mine": mine,
        "sort": sort, "sort_label": SORT_OPTIONS[sort][0], "state": state,
        "sort_options": [(key, value[0]) for key, value in SORT_OPTIONS.items()],
        "pagination_query": urlencode(filters),
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
    return Post.objects.filter(visible).defer("search_text")


@require_safe
@never_cache
def post_detail(request, pk):
    post = get_object_or_404(_readable_posts(request).select_related("author").prefetch_related("categories"), pk=pk)
    return render(request, "post_detail.html", {"post": post, "note_text": plain_text(post.content)})


@require_safe
def download_post(request, pk):
    post = get_object_or_404(_readable_posts(request), pk=pk)
    response = HttpResponse(f"{post.title}\n\n{plain_text(post.content)}\n", content_type="text/plain; charset=utf-8")
    # Use a generated filename rather than putting user-provided titles in headers.
    response["Content-Disposition"] = f'attachment; filename="note-{post.pk}.txt"'
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
    return render(request, "signup.html", {"form": form})


def about(request):
    return render(request, "about.html")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def create_post(request):
    form = PostForm(request.POST if request.method == "POST" else None)
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
        messages.success(request, "Your note has been published." if post.is_published else "Your draft has been saved.")
        return redirect("home" if post.is_published else "my-notes")
    return render(request, "post_form.html", {"form": form})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def edit_post(request, pk):
    # Scope the lookup itself: hiding edit controls does not protect direct requests.
    post = get_object_or_404(Post, pk=pk, author__user=request.user)
    form = PostForm(request.POST if request.method == "POST" else None, instance=post)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Your note has been updated.")
        return redirect("post-detail", pk=post.pk)
    return render(request, "post_form.html", {"form": form, "post": post})


@login_required
@require_http_methods(["GET", "POST"])
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk, author__user=request.user)
    # GET only shows confirmation; deletion requires a CSRF-protected POST.
    if request.method == "POST":
        post.delete()
        messages.success(request, "Your note has been deleted.")
        return redirect("my-notes")
    return render(request, "post_confirm_delete.html", {"post": post})
