from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PostForm
from .models import Author, Post


def home(request):
    posts = Post.objects.select_related("author").prefetch_related("categories")
    return render(request, "index.html", {"posts": posts})


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST if request.method == "POST" else None)
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
        author, _ = Author.objects.get_or_create(
            user=request.user,
            defaults={"user_name": request.user.get_username()[:20]},
        )
        post = form.save(commit=False)
        post.author = author
        post.save()
        form.save_m2m()
        messages.success(request, "The post has been created successfully.")
        return redirect("home")
    return render(request, "post_form.html", {"form": form})
