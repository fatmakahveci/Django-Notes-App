from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('index.html', views.home, name='index'),
    path('about.html', views.about, name='about'),
    path('login.html', views.login, name='login'),
    path('signup.html', views.signup, name='signup'),
    path('logout.html', views.logout, name='logout'),
    path('post_form.html', views.create_post, name='post-form'),
]
