# Django Notes App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Notes-App)](https://github.com/fatmakahveci/Django-Notes-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A Django application for writing and sharing notes, with user accounts, optional categories, and a rich-text editor.

## Demo

![Django Notes demo showing registration, note creation, category selection, and login/logout](demo.gif)

A 22-second walkthrough of creating an account, publishing a categorized note,
and signing out and back in.

## Features

- Register, log in, and log out with Django authentication
- Write notes with TinyMCE; authors are assigned from the signed-in account
- Organize notes with optional categories managed through Django admin
- Browse a public feed with authors, publication dates, and categories
- Run locally with SQLite or Docker Compose

Built with **Python**, **Django 5.2**, **TinyMCE**, and **SQLite**.

## Getting Started

### Prerequisites

- Python 3.11 or newer
- pip

### Installation

Clone the repository and run all commands from its root directory:

```bash
git clone https://github.com/fatmakahveci/Django-Notes-App.git
cd Django-Notes-App
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python my_site/manage.py migrate
python my_site/manage.py runserver
```

Open http://127.0.0.1:8000.

## Using the App

1. Select **Register** to create an account. Registration signs you in automatically.
2. Select **Create a new post**, enter a title and content, and optionally choose categories.
3. Select **Save** to publish the note in the public feed.
4. Use **Log out** to end your session and **Log in** to return.

All published notes are visible to everyone, including visitors who are not
signed in. To manage categories, create an administrator account:

```bash
python my_site/manage.py createsuperuser
```

Then sign in at http://127.0.0.1:8000/admin/ and add categories.

The editor stores rich text; the public feed displays a plain-text preview to
avoid rendering untrusted HTML.

## Docker (Local Development)

From the repository root:

```bash
docker compose up --build
```

Docker with the Compose plugin is required. Open http://127.0.0.1:8000. Migrations run automatically and SQLite data persists
in the `notes-data` volume. This uses Django's development server.

To create an administrator while the service is running:

```bash
docker compose exec web python manage.py createsuperuser
```

Stop the service with `docker compose down`; the database volume is retained.

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

Run from the repository root with the virtual environment activated:

```bash
python my_site/manage.py check
python my_site/manage.py makemigrations --check --dry-run
python my_site/manage.py test blog_app
```

CI runs these checks on pushes and pull requests to `main`.

## Repository Structure

```text
Django-Notes-App/
├── demo.gif                 # Application walkthrough
├── docker-compose.yml      # Local Docker setup
├── requirements.txt        # Dependency entry point
└── my_site/
    ├── manage.py           # Django management commands
    ├── blog_app/           # Models, forms, views, tests, and migrations
    ├── my_site/            # Settings and root URL configuration
    ├── static/             # Styles and static assets
    └── templates/          # Server-rendered pages
```

## Project Resources

- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE.md)
