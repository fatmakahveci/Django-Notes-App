![header.png](header.png)

# Note App

🎯 A project for learning purposes.

🦦 You can check my [Django](https://fatmakahveci.com/django-note/django/) and [python](https://fatmakahveci.com/python-note/) notes in my blog.

## Installation

```bash
# Clone the repository
git clone https://github.com/fatmakahveci/Django-Notes-App.git
```

```bash
# Go to the directory
cd Django-Notes-App
```

```bash
# Create a virtual environment
python3 -m venv .venv
```

```bash
# Activate the virtual environment
source .venv/bin/activate
```

```bash
# Install packages
pip install -r my_site/blog_app/requirements.txt
```

```bash
cd my_site
```

```bash
python manage.py migrate
```

```bash
python manage.py runserver
```

## Production configuration

Set the following environment variables before starting the application in production:

```bash
export DJANGO_DEBUG=false
export DJANGO_SECRET_KEY='replace-with-a-long-random-secret'
export DJANGO_ALLOWED_HOSTS='notes.example.com'
```

The application refuses to start in production without an explicit secret key. HTTPS redirect, secure cookies, and HSTS are enabled automatically when debug mode is disabled.
