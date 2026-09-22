from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('index.html', views.home, name='index'),
    path('about.html', views.about, name='about'),
    path('login.html', LoginView.as_view(template_name="login.html"), name='login'),
    path('signup.html', views.signup, name='signup'),
    path('logout.html', LogoutView.as_view(), name='logout'),
    path('post_form.html', views.create_post, name='post-form'),
]
