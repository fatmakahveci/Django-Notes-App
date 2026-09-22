from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import operations, views
from .forms import LoginForm

urlpatterns = [
    path("notes/autosave/", views.autosave, name="note-autosave"),
    path("notes/<int:pk>/autosave/", views.autosave, name="post-autosave"),
    path("health/", operations.health, name="health"),
    path("notes/<int:pk>/history/", views.history, name="post-history"),
    path("notes/<int:pk>/pin/", views.pin_note, name="post-pin"),
    path("notes/bulk/", views.bulk_notes, name="bulk-notes"),
    path("notes/transfer/", views.transfer_notes, name="transfer-notes"),
    path("notes/export/", views.export_collection, name="export-notes"),
    path("notes/trash/", views.trash, name="trash"),
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
        LoginView.as_view(template_name="accounts/login.html", authentication_form=LoginForm),
        name="login",
    ),
    path("signup.html", views.signup, name="signup"),
    path("logout.html", LogoutView.as_view(), name="logout"),
    path("post_form.html", views.create_post, name="post-form"),
]
