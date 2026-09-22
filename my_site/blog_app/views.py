from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PostForm, SignupForm
from .models import Author, Category, Post


def _post_list(request, *, mine=False):
    posts = Post.objects.select_related("author").prefetch_related("categories")
    if mine:
        posts = posts.filter(author__user=request.user)
    query = request.GET.get("q", "").strip()[:200]
    category = request.GET.get("category", "")
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(content__icontains=query))
    if category:
        if category.isascii() and category.isdigit() and len(category) <= 18:
            posts = posts.filter(categories__pk=int(category))
        else:
            posts = posts.none()
    page = Paginator(posts.order_by("-publish_time", "-pk"), 10).get_page(request.GET.get("page"))
    filters = {key: value for key, value in {"q": query, "category": category}.items() if value}
    return render(request, "index.html", {
        "posts": page, "page_obj": page, "query": query, "selected_category": category,
        "categories": Category.objects.order_by("title", "pk"), "mine": mine,
        "pagination_query": urlencode(filters),
    })


def home(request):
    return _post_list(request)


@login_required
def my_notes(request):
    return _post_list(request, mine=True)


def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related("author").prefetch_related("categories"), pk=pk)
    return render(request, "post_detail.html", {"post": post})


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
@require_http_methods(["GET", "POST"])
def create_post(request):
    form = PostForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            author, _ = Author.objects.get_or_create(
                user=request.user, defaults={"user_name": request.user.get_username()},
            )
            post = form.save(commit=False)
            post.author = author
            post.save()
            form.save_m2m()
        messages.success(request, "The post has been created successfully.")
        return redirect("home")
    return render(request, "post_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def edit_post(request, pk):
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
    if request.method == "POST":
        post.delete()
        messages.success(request, "Your note has been deleted.")
        return redirect("my-notes")
    return render(request, "post_confirm_delete.html", {"post": post})
