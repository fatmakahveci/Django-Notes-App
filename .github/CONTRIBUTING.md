# Contributing

Bug fixes, documentation improvements, and focused features are welcome.
Check existing issues and pull requests before starting. For a larger change,
open an issue describing the problem and proposed approach first.

Report vulnerabilities privately using the [security policy](../SECURITY.md).

## Set up your workspace

Follow the [README](../README.md#run-it-locally) to install Python dependencies
and initialize the database, then install the development tools:

```bash
python -m pip install -r requirements-dev.txt
```

Create a branch from the latest `main`. Keep local databases, credentials, and
virtual environments out of commits. `.env.example` lists the supported settings;
the application reads environment variables and does not load `.env` files itself.

## Make a change

Keep each pull request focused on one problem. Follow the surrounding code style
and the whitespace settings in `.editorconfig`. Update tests when behavior changes,
and update the README when setup or usage changes.

Database changes need a migration. Do not edit migrations that have already been
released. Third-party files under `my_site/static/vendor/` should remain unmodified;
follow their upstream update notes when replacing them.

## Check your work

Run these commands from the repository root with your virtual environment active:

```bash
python scripts/check.py --audit
```

The script runs system checks, migration checks, tests, and the optional dependency
audit in order. Omit `--audit` to run without the network-dependent audit. CI uses
the same script for the application checks.

The project does not currently configure a separate linter or type checker.

For Docker changes, also validate and build the image:

```bash
docker compose config --quiet
docker build -f my_site/blog_app/Dockerfile -t django-notes:local .
docker run --rm django-notes:local python manage.py test blog_app
```

For interface changes, run the browser regression test:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts/test_browser.py
```

It starts its own server and uses an isolated test database with synthetic accounts.
Check any additional navigation, forms, and note actions on mobile and desktop. For permission changes, test anonymous visitors, the note's author, and
another signed-in user, including direct POST requests. Never use real account
data in screenshots or test fixtures.

## Open a pull request

Explain the problem, what changed, and how you checked it. Link related issues
and include screenshots for visible interface changes. Note any migrations or
configuration changes that a maintainer needs to apply.

Before submitting, review the diff for unrelated edits, generated files, secrets,
and personal information. CI runs the application tests, Docker checks, and Python
dependency audit; resolve failures before requesting a merge.
