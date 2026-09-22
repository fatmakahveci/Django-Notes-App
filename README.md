# Django Notes App

[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A small Django app for writing notes and sharing them. Create an account, jot something down, and come back to edit it later. Categories and search help you find things as your collection grows.

**Published notes are public.** Choose **Draft** in the visibility field to keep a note visible only to you and administrators. “My notes” collects both your drafts and published posts. Only you can edit or delete your notes through the app; administrators can also manage them in Django admin.

The app uses Django 6.1, TinyMCE, Bootstrap 5.3.8, and SQLite. It works on desktop and mobile, with a searchable feed, category filters, and a separate page for each note.

## Run it locally

You'll need Python 3.12 or newer and pip. Copy this repository's clone URL from the **Code** menu, then replace `<repository-url>` below with it:

```bash
git clone <repository-url>
cd Django-Notes-App
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python my_site/manage.py migrate
python my_site/manage.py runserver
```

Open http://127.0.0.1:8000 and you're ready to go. On Windows PowerShell, replace the activation command with `.venv\Scripts\Activate.ps1`.

Already have a checkout? After pulling the latest code, activate your virtual environment, install the requirements again, and run `migrate`. Migration `0012` adds drafts while keeping existing notes published. If that environment still uses Python 3.11, recreate it with Python 3.12 or newer first.

## Write your first note

Choose **Register** to create an account. You'll be signed in automatically. Then select **Create a new post**, add a title and some text, and choose a visibility. New notes default to **Published**; choose **Draft** to keep writing privately. Hit **Save** when ready. Categories are optional, so you can leave them unchecked.

Published notes appear in the public feed. Drafts appear only in **My notes**. To publish a draft, edit it, change its visibility to **Published**, and save. Open its title or **Read note** to read it in full. On your own notes, you'll also see **Edit note** and **Delete note**; deleting asks you to confirm first.

Use **Search notes** and **Category** to find something, or **My notes** to see just your posts. Sort by newest, oldest, or title, and click a category label to filter the list. **My notes** also lets you show just drafts or published notes. The feed shows 10 notes per page and keeps your filters and sort order as you move between pages.

One detail about formatting: TinyMCE stores rich text, but the reading pages show plain text with paragraph and line breaks. Bold text and embedded images won't appear there. Feed previews stop at 400 characters; the note page shows the full text.

The editor shows a word count and warns before you leave with unsaved changes. Press **Ctrl+Enter** (or **⌘+Enter** on macOS) to save. These helpers need JavaScript; the forms also work without it. Unsaved text stays in the current page and is not backed up automatically.

On a note page, use **Copy text**, **Download .txt**, or **Print** to take your writing elsewhere. Copy needs clipboard permission and a secure browser context; downloading works without JavaScript. Draft downloads use the same owner check as draft pages.

### Add categories

Categories are managed in Django admin. Create an administrator account from the repository root:

```bash
python my_site/manage.py createsuperuser
```

Then sign in at http://127.0.0.1:8000/admin/ to add them. You can write notes without setting up any categories.

## Prefer Docker?

With Docker and its Compose plugin installed, run:

```bash
docker compose up --build
```

The app will be at http://127.0.0.1:8000. Migrations run on startup, and your SQLite database is kept in the `notes-data` volume at `/data/db.sqlite3`.

To create an admin account while the container is running:

```bash
docker compose exec web python manage.py createsuperuser
```

Use `docker compose down` to stop it; your database stays in the volume. After changing the code, run `docker compose up --build` again. This setup uses Django's development server and is intended for local use.

Compose checks the app's health automatically. Run `docker compose ps` to see
whether the service is healthy. The `/health/` endpoint returns HTTP 200 with
`{"status": "ok"}` when the notes table can be read, or HTTP 503 when the database
or table is unavailable. It returns no note or account data and is not cached.
This is a database readiness check, not a complete check of external services or
pending migrations. A failed check marks the container unhealthy; it does not
restart it automatically.

## Settings

The app reads these environment variables directly. [.env.example](.env.example) lists them with setup notes; it doesn't load a `.env` file automatically. For Docker, set them in the Compose service's `environment` section.

| Variable | Default | What it controls |
| --- | --- | --- |
| `DJANGO_DEBUG` | `true` | Development mode |
| `DJANGO_SECRET_KEY` | Development-only key | Required when debug is disabled |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `DJANGO_DATABASE_PATH` | `my_site/db.sqlite3` | SQLite database location |

For a production deployment, set `DJANGO_DEBUG=false`, supply a private secret key and your allowed hosts, and configure HTTPS. Use a production WSGI/ASGI server and serve the static files collected by `python my_site/manage.py collectstatic`. Turning debug off also enables secure cookies and HTTPS redirects.

With your production environment variables set, check the configuration with:

```bash
python my_site/manage.py check --deploy
```

### Login and signup limits

Login attempts are limited to 20 per IP address and 10 per username every 10 minutes. This includes successful logins and Django admin logins. Signup allows 5 attempts per IP address per hour. Once a limit is reached, the app returns HTTP 429 with a `Retry-After` header.

The counters are stored in the database so they work across app processes. You can change the limits in `AUTH_ATTEMPT_LIMITS` in the Django settings. GET requests and requests rejected by CSRF protection don't count.

If you're running behind a reverse proxy, configure the trusted server layer to pass along the real client address. The app uses `REMOTE_ADDR` rather than trusting forwarding headers from the client.

## Working on the code

Dependencies are split by purpose; the optional files include the application
requirements automatically.

| File | Installs |
| --- | --- |
| `requirements.txt` | Django and the editor integration |
| `requirements-dev.txt` | Application dependencies and `pip-audit` |
| `requirements-browser.txt` | Application dependencies and Playwright |

With your virtual environment active, run these from the repository root:

```bash
python scripts/check.py
```

This runs Django's system checks, checks for missing migrations, and runs the
application tests. It stops at the first failure and uses your active Python
environment. CI uses the same command.

The tests cover signing in, ownership permissions, editing and deletion, search, pagination, text rendering, migrations, CSRF, and authentication limits.

To check Python dependencies for known vulnerabilities:

```bash
python -m pip install -r requirements-dev.txt
python scripts/check.py --audit
```

The optional audit covers application, development, and browser-test dependencies
and needs network access. You can still run individual Django
commands through `python my_site/manage.py` when working on a specific test.

CI runs these checks on pushes and pull requests to `main`, along with Docker tests and static file collection. The dependency audit covers Python packages, not bundled JavaScript. Dependabot checks the application and development requirements for updates.

The editor uses a local copy of TinyMCE 7.9.3 because the Django package bundles an older version. Its [source and update notes](my_site/static/vendor/tinymce-7.9.3/UPSTREAM.md) explain how to keep it patched.

The writing workflow also has a browser test, using a temporary test database:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python scripts/test_browser.py
```

CI runs it in Chromium. It covers draft privacy, publishing, unsaved-change warnings,
keyboard saving, downloads, clipboard feedback, print layout, and mobile sizing.

Most of the app code lives in `my_site/blog_app/`. Page templates are in `my_site/templates/`, styles and other assets are in `my_site/static/`, and Django settings are in `my_site/my_site/`.

For more detail, see the [contributing guide](.github/CONTRIBUTING.md) and [changelog](CHANGELOG.md). To report a security issue, follow the [security policy](SECURITY.md).

## License

[Apache 2.0](LICENSE.md).
