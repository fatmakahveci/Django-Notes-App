# Security Policy

## Supported Versions

Security updates are provided for the latest code on the `main` branch.
Older releases and unmaintained branches may not receive security fixes.

## Reporting a Vulnerability

Please do not disclose security vulnerabilities in public issues, discussions,
or pull requests.

Report a vulnerability through this repository's
[private vulnerability reporting](https://github.com/fatmakahveci/Django-Notes-App/security/advisories/new).
If that option is unavailable, contact the repository owner through the
[GitHub profile](https://github.com/fatmakahveci) to arrange a private reporting
channel.

Include the affected component and version, reproduction steps, potential
impact, and any suggested mitigation. Reports will be reviewed as promptly as
possible, and coordinated disclosure is appreciated.

## Application Security

- Published notes are public, including to visitors who are not signed in.
  Do not store passwords, credentials, or confidential information in notes.
- Creating a note requires authentication. The application assigns its author
  from the signed-in account. Editing and deleting require ownership, verified
  on the server for both GET and POST requests. Deletion only occurs on POST.
- The public feed and detail page display note content as plain text. Do not render stored
  rich-text HTML with the `safe` template filter without appropriate sanitization.
- Keep Django's CSRF middleware and tokens enabled for forms that change data.

## Authentication Limits

Public and admin login attempts share limits of 20 attempts per IP and 10 per
username per 10-minute fixed window. Signup is limited to 5 attempts per IP per
hour. All attempts count, including successful submissions. Exceeding a limit
returns HTTP 429 and a `Retry-After` header without processing authentication.
CSRF-rejected requests and GET requests do not consume attempts.

Counters are stored in the database and incremented atomically across workers.
Identifiers are keyed hashes, not plaintext usernames or IP addresses. Expired
counters are deleted on subsequent authentication attempts. Changing the secret
key also changes the counter keys. Configure limits in `AUTH_ATTEMPT_LIMITS`.

Only `REMOTE_ADDR` is used for the client IP. Forwarding headers are not trusted.
If deploying behind a proxy, configure the trusted server layer to supply the
real client IP; otherwise clients behind that proxy share its IP quota. These
limits complement, rather than replace, infrastructure-level abuse protection.

## Dependency Checks

CI runs `pip-audit --strict -r requirements.txt` and fails on known Python package
vulnerabilities or dependency collection errors. This does not scan JavaScript
bundled with TinyMCE or fetched from the Bootstrap CDN. Bootstrap assets use
version-specific integrity hashes. Review upstream editor and frontend advisories
alongside Python dependency updates.

## Deployment

The default configuration and Docker Compose service are for local development.
Before deploying to production:

- Set `DJANGO_DEBUG=false` and provide a private `DJANGO_SECRET_KEY`.
- Set `DJANGO_ALLOWED_HOSTS` to the hostnames you serve.
- Configure HTTPS, a production WSGI/ASGI server, and static file serving.
- Protect the SQLite database, backups, and administrator credentials.
- Keep dependencies updated and review security fixes before deployment.

Run Django's deployment checks with your production environment variables set:

```bash
python my_site/manage.py check --deploy
```

Settings read environment variables from the process; `.env` files are not
loaded automatically. Never commit secrets or production database files.
