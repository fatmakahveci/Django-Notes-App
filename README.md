# Django Notes App

[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A small Django app for writing notes and sharing them. Create an account, jot something down, and come back to edit it later. Categories and search help you find things as your collection grows.

Notes are **public**. “My notes” brings your own posts together, but doesn't make them private. Only you can edit or delete your notes through the app; administrators can also manage them in Django admin.

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

Already have a checkout? After pulling the latest code, activate your virtual environment, install the requirements again, and run `migrate`. If that environment still uses Python 3.11, recreate it with Python 3.12 or newer first.

## Write your first note

Choose **Register** to create an account. You'll be signed in automatically. Then select **Create a new post**, add a title and some text, and hit **Save**. Categories are optional, so you can leave them unchecked.

Your note will appear in the feed, newest first. Open its title or **Read note** to read it in full. On your own notes, you'll also see **Edit note** and **Delete note**; deleting asks you to confirm first.

Use **Search notes** and **Category** to find something, or **My notes** to see just your posts. The feed shows 10 notes per page and keeps your filters as you move between pages.

One detail about formatting: TinyMCE stores rich text, but the reading pages show plain text with paragraph and line breaks. Bold text and embedded images won't appear there. Feed previews stop at 400 characters; the note page shows the full text.

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

With your virtual environment active, run these from the repository root:

```bash
python my_site/manage.py check
python my_site/manage.py makemigrations --check --dry-run
python my_site/manage.py test blog_app
```

The tests cover signing in, ownership permissions, editing and deletion, search, pagination, text rendering, migrations, CSRF, and authentication limits.

To check Python dependencies for known vulnerabilities:

```bash
python -m pip install -r requirements-dev.txt
python -m pip_audit --strict -r requirements.txt
```

CI runs these checks on pushes and pull requests to `main`, along with Docker tests and static file collection. The dependency audit covers Python packages, not bundled JavaScript. Dependabot checks the application and development requirements for updates.

The editor uses a local copy of TinyMCE 7.9.3 because the Django package bundles an older version. Its [source and update notes](my_site/static/vendor/tinymce-7.9.3/UPSTREAM.md) explain how to keep it patched.

Most of the app code lives in `my_site/blog_app/`. Page templates are in `my_site/templates/`, styles and other assets are in `my_site/static/`, and Django settings are in `my_site/my_site/`.

For more detail, see the [contributing guide](.github/CONTRIBUTING.md) and [changelog](CHANGELOG.md). To report a security issue, follow the [security policy](SECURITY.md).

## License

[Apache 2.0](LICENSE.md).
