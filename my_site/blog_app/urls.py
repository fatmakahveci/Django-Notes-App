from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import operations, views
from .forms import LoginForm

urlpatterns = [
    path("health/", operations.health, name="health"),
    path("notes/mine/", views.my_notes, name="my-notes"),
    path("notes/<int:pk>/", views.post_detail, name="post-detail"),
    path("notes/<int:pk>/download/", views.download_post, name="post-download"),
    path("notes/<int:pk>/edit/", views.edit_post, name="post-edit"),
    path("notes/<int:pk>/delete/", views.delete_post, name="post-delete"),
    path("", views.home, name="home"),
    path("index.html", views.home, name="index"),
    path("about.html", views.about, name="about"),
    path(
        "login.html",
        LoginView.as_view(template_name="login.html", authentication_form=LoginForm),
        name="login",
    ),
    path("signup.html", views.signup, name="signup"),
    path("logout.html", LogoutView.as_view(), name="logout"),
    path("post_form.html", views.create_post, name="post-form"),
]
