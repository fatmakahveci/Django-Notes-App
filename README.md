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
python -m pip install -r requirements.txt
cd my_site
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Using the App

Register an account, log in, and select **Create a new post**. Posts are public,
and their author is assigned from the signed-in account. Categories are optional;
create them in the admin using a superuser:

```bash
python my_site/manage.py createsuperuser
```

The editor stores rich text; the public feed displays a plain-text preview to
avoid rendering untrusted HTML.

## Docker (Local Development)

From the repository root:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Migrations run automatically and SQLite data persists
in the `notes-data` volume. This uses Django's development server.

## Configuration

Settings read environment variables from the process; `.env` is not loaded automatically.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_DEBUG` | `true` | Development mode |
| `DJANGO_SECRET_KEY` | Development-only key | Required when debug is disabled |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `DJANGO_DATABASE_PATH` | `my_site/db.sqlite3` | SQLite database path |

For production, set `DJANGO_DEBUG=false`, provide a private secret key and allowed
hosts, configure HTTPS and a production WSGI/ASGI server, and serve the output of
`python my_site/manage.py collectstatic`. Secure cookies and HTTPS redirects are
enabled when debug is disabled.

## Quality Checks

Run from the repository root:


```bash
python my_site/manage.py check
python my_site/manage.py makemigrations --check --dry-run
python my_site/manage.py test blog_app
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
