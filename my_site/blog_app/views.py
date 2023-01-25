from .models import Post
from .forms import PostForm
from django.contrib import messages
from django.shortcuts import render, redirect

from django.http import HttpResponse

def home(request):
    posts = Post.objects.all()
    context = {"posts": posts}
    return render(request, 'index.html', context)

def login(request):
    context = {}
    return render(request, "login.html", context)

def signup(request):
    context = {}
    return render(request, "signup.html", context)

def logout(request):
    context = {}
    return render(request, "logout.html", context)

def about(request):
    context = {}
    return render(request, "about.html", context)

def create_post(request):
    if request.method == 'GET':
        context = {'form': PostForm()}
        return render(request, 'post_form.html', context)
    elif request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'The post has been created successfully.')
            return redirect('index.html')
        else:
            messages.error(request, 'The post cannot be created.')
            return render(request, 'post_form.html', {'form': form})
