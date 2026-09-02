# Django Notes App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Notes-App)](https://github.com/fatmakahveci/Django-Notes-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A server-rendered Django application for organizing authored posts with categories, authentication screens, and rich-text editing.

## Highlights

- Post, author, and category domain models
- Account signup, login, and logout routes
- Rich-text editing with Django TinyMCE
- Environment-driven production security settings

## Technology

- Python
- Django
- Django REST Framework
- TinyMCE
- SQLite

## Getting Started

### Prerequisites

- Python 3.11 or newer
- pip

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r my_site/blog_app/requirements.txt
cd my_site
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Quality Checks

```bash
cd my_site && python manage.py check
cd my_site && python manage.py test
```

## Repository Structure

- `my_site/blog_app` — models, views, URLs, and dependencies
- `my_site/templates` — server-rendered pages
- `my_site/my_site` — project settings and root routing

## Project Resources

- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE.md)
