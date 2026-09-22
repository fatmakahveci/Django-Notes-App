# Security Policy

## Supported Versions

Security updates are provided for the latest code on the `main` branch.
Older releases and unmaintained branches may not receive security fixes.

## Reporting a Vulnerability

Please do not disclose security vulnerabilities in public issues, discussions,
or pull requests.

On this repository's GitHub page, open **Security → Advisories → Report a
vulnerability** to send a private report. If that option is unavailable, ask
a maintainer to enable private reporting without including vulnerability details
in the request.

Include the affected component and version, reproduction steps, potential
impact, and any suggested mitigation. Reports will be reviewed as promptly as
possible, and coordinated disclosure is appreciated.

## Application Security

- Published notes are public, including to visitors who are not signed in.
  Do not store passwords, credentials, or confidential information in notes.
- Drafts are excluded from public feeds and searches. Their detail and download
  endpoints require the owner; administrators can manage them through Django admin.
  Draft-related pages and downloads send `Cache-Control: private, no-store`.
- Creating a note requires authentication. The application assigns its author
  from the signed-in account. Editing and deleting require ownership, verified
  on the server for both GET and POST requests. Deletion only occurs on POST.
- Feed previews remain escaped plain text. Detail and history pages sanitize rich
  text with an explicit nh3 allowlist before marking it safe. Scripts, active
  embeds, inline styles, and unsafe URL schemes are not allowed.
- Recovery copies, version history, Trash, tags, and collection exports require
  the owner. Autosave never publishes changes. Imports and restored versions are
  always private drafts. Bulk operations validate ownership of the whole selection.
- Markdown imports disable raw HTML. ZIP imports validate filenames, sizes,
  member counts, and metadata before writing anything; files are never extracted.
- Requests over 26 MiB are rejected by their declared length before parsing.
  A streaming upload handler also caps combined file data at 25 MiB before it
  reaches temporary storage; exceeding either limit returns HTTP 413 and imports
  nothing. Normal uploads still require CSRF validation.
- Deleting moves notes to Trash. Permanent deletion requires an explicit POST
  confirmation and removes the note's revisions. Protect backups as private data.
- Keep Django's CSRF middleware and tokens enabled for forms that change data.

## Authentication Limits

Public and admin login attempts share limits of 20 attempts per IP and 10 per
username per 10-minute fixed window. Signup is limited to 5 attempts per IP per
hour. All attempts count, including successful submissions. Exceeding a limit
returns HTTP 429 and a `Retry-After` header without processing authentication.
CSRF-rejected requests and GET requests do not consume attempts.
Username counters use the same Unicode normalization as Django login forms,
so equivalent spellings share a limit.

Counters are stored in the database and incremented atomically across workers.
Identifiers are keyed hashes, not plaintext usernames or IP addresses. Expired
counters are deleted on subsequent authentication attempts. Changing the secret
key also changes the counter keys. Configure limits in `AUTH_ATTEMPT_LIMITS`.

By default, only `REMOTE_ADDR` is used for the client IP; forwarding headers are
ignored. The separate production stack enables `DJANGO_TRUST_PROXY_HEADERS`
only on its isolated backend. Caddy overwrites `X-Real-IP` and
`X-Forwarded-Proto`, and Django validates the client address before using it for
rate limits. Do not enable this setting on a directly accessible app server.
If adding another proxy, configure its trusted client-IP handling; otherwise
clients behind that proxy share its IP quota. These
limits complement, rather than replace, infrastructure-level abuse protection.

## Dependency Checks

CI audits application, development, and browser-test requirements with `pip-audit --strict`
and fails on known Python package
vulnerabilities or dependency collection errors. This does not scan JavaScript
bundled with TinyMCE or fetched from the Bootstrap CDN. Bootstrap assets use
version-specific integrity hashes. Review upstream editor and frontend advisories
alongside Python dependency updates.

Both note forms and Django admin load the patched local TinyMCE 7.9.3 runtime,
not the older runtime bundled with django-tinymce. See the vendored
[source and update notes](src/static/vendor/tinymce-7.9.3/UPSTREAM.md).
Unused compressor, file-browser, and flatpage-list endpoints are not exposed.

## Deployment

The default configuration and Docker Compose service are for local development.
The separate `compose.production.yml` uses Gunicorn and Caddy with HTTPS, a private
backend network, proxy upload limits, and static file serving. Follow the
[deployment guide](docs/deployment.md) and run `python scripts/test_production.py`
to check this configuration with a local certificate before deploying it.
The image runs as UID/GID `10001`; Compose drops Linux capabilities and prevents
privilege escalation. Its port is bound to the loopback interface.
Before deploying to production:

- Set `DJANGO_DEBUG=false` and provide a private `DJANGO_SECRET_KEY`.
- Set `DJANGO_ALLOWED_HOSTS` to the hostnames you serve.
- Configure HTTPS, a production WSGI/ASGI server, and static file serving.
- Limit request sizes and timeouts at the proxy/server too. An ASGI server or
  proxy may buffer a request before Django's upload handler receives it.
- Protect the SQLite database, backups, and administrator credentials.
- Keep dependencies updated and review security fixes before deployment.

Run Django's deployment checks with your production environment variables set:

```bash
python src/manage.py check --deploy
```

Settings read environment variables from the process; `.env` files are not
loaded automatically. Never commit secrets or production database files.
