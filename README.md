# Django Notes App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Notes-App)](https://github.com/fatmakahveci/Django-Notes-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A Django application for writing and sharing notes, with user accounts, optional categories, and a rich-text editor.

## Demo

![Django Notes demo showing registration, note creation, category selection, and login/logout](demo.gif)

A 22-second walkthrough of creating an account, publishing a categorized note,
and signing out and back in. The recording predates the current layout,
search, pagination, and note-management features.

## Features

- Register, log in, and log out with Django authentication
- Write notes with TinyMCE and optional categories
- Read 400-character previews in a paginated feed and open full note details
- Search titles and content, filter by category, and browse **My notes**
- Edit or delete your own notes, with confirmation before deletion
- Use consistent forms and a responsive desktop/mobile layout
- Limit login and signup attempts with shared database counters
- Run locally with SQLite or Docker Compose

Built with **Python**, **Django 5.2 LTS**, **TinyMCE**, **Bootstrap 5.3.8**, and **SQLite**.

## Getting Started

### Prerequisites

- Python 3.11 or newer (CI and Docker use Python 3.12)
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

Open http://127.0.0.1:8000. The activation command above is for macOS/Linux;
on Windows PowerShell, use `.venv\Scripts\Activate.ps1`.

### Updating an Existing Installation

After obtaining the latest code, activate your virtual environment and run from
the repository root:

```bash
python -m pip install -r requirements.txt
python my_site/manage.py migrate
python my_site/manage.py runserver
```

Migrations make categories optional, preserve full author names, and create
authentication attempt counters. Previously truncated author names are restored
when they match the linked account's first 20 characters; custom names are preserved.

## Using the App

1. Select **Register** to create an account; registration signs you in automatically.
2. Select **Create a new post**, enter a title and visible text, and optionally choose categories.
3. Select **Save** to publish. The feed shows 10 notes per page, newest first.
4. Use **Search notes** and **Category**, then **Apply**, to narrow the list.
   Filters remain active when you select **Previous** or **Next**.
5. Open a title or **Read note** to see the full note. Owners see **Edit note**
   and **Delete note**. Deletion requires a separate confirmation.
6. Select **My notes** to browse your own posts, or **Log out** to end your session.

**All published notes are public**, including those listed under **My notes**.
Only the author can edit or delete a note through the application. Administrators
can manage posts and categories through Django admin.

Create an administrator account from the repository root:

```bash
python my_site/manage.py createsuperuser
```

Sign in at http://127.0.0.1:8000/admin/ to add categories. Categories are optional
in both the note form and admin. Blank editor markup is rejected by the note form.

The editor stores rich text. The feed and detail pages display escaped plain text
with paragraph and line breaks; bold formatting and embedded images are not
rendered. Feed previews are limited to 400 characters; details show the full text.

### Authentication Limits

All login POST attempts, including successful attempts and admin logins, count
against shared fixed windows: **20 per IP address and 10 per username every
10 minutes**. Registration allows **5 attempts per IP address per hour**.
Exceeding a limit returns HTTP 429 with a `Retry-After` header. GET requests and
requests rejected by CSRF protection do not consume the quota.

Counters live in the database, so they are shared across application processes.
Expired counters are removed on subsequent authentication attempts. Limits are
configured in `AUTH_ATTEMPT_LIMITS` in the Django settings. The application uses
`REMOTE_ADDR`, not client-supplied forwarding headers; behind a reverse proxy,
configure the trusted server layer to provide the actual client address.

## Docker (Local Development)

With Docker and its Compose plugin installed, run from the repository root:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. Migrations run automatically and SQLite data persists
in the `notes-data` volume at `/data/db.sqlite3`. This uses Django's development
server. After code changes, run `docker compose up --build` again to rebuild
the image.

To create an administrator while the service is running:

```bash
docker compose exec web python manage.py createsuperuser
```

Stop the service with `docker compose down`; the database volume is retained.

## Configuration

Settings read environment variables from the process; `.env` is not loaded automatically.
For Docker, configure variables in the Compose service's `environment` section.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_DEBUG` | `true` | Development mode |
| `DJANGO_SECRET_KEY` | Development-only key | Required when debug is disabled |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `DJANGO_DATABASE_PATH` | `my_site/db.sqlite3` | SQLite database path |

For production, set `DJANGO_DEBUG=false`, provide a private secret key and allowed
hosts, configure HTTPS and a production WSGI/ASGI server, and serve the output of
`python my_site/manage.py collectstatic`. Secure cookies and HTTPS redirects are
enabled when debug is disabled. Validate your production configuration with its
environment variables set:

```bash
python my_site/manage.py check --deploy
```

## Quality Checks

Run from the repository root with the virtual environment activated:

```bash
python my_site/manage.py check
python my_site/manage.py makemigrations --check --dry-run
python my_site/manage.py test blog_app
```

Tests cover authentication, CSRF, ownership checks, editing/deletion, text
rendering, filtering, pagination, migration, and authentication limits.

To run the Python dependency vulnerability scan:

```bash
python -m pip install -r requirements-dev.txt
python -m pip_audit --strict -r requirements.txt
```

CI runs tests and migration checks, builds and tests the Docker image, collects
static files, and audits Python dependencies on pushes and pull requests to `main`.
The audit checks known advisories for Python packages; it does not audit bundled
JavaScript. Dependabot monitors application and development requirements.

## Repository Structure

```text
Django-Notes-App/
├── demo.gif                 # Application walkthrough
├── docker-compose.yml      # Local Docker setup
├── requirements.txt        # Application dependency entry point
├── requirements-dev.txt    # Development and audit tooling
├── SECURITY.md             # Security policy
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
- [Security policy](SECURITY.md)
- [License](LICENSE.md)
