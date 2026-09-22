# Deploying Django Notes

The production stack uses Gunicorn for Django and Caddy for HTTPS and static
files. It is intended for a single host with persistent Docker volumes and
SQLite. One synchronous Gunicorn worker keeps writes serialized. Move to a
server database and review concurrency before scaling to multiple workers or hosts.

## First deployment

You need a server with Docker Compose, a hostname pointing to it, and inbound TCP
ports 80 and 443. Use this Compose file on its own; combining it with the development
file would expose the app port and enable development settings.

Create `.env.production` in the repository root (Git and Docker builds ignore it):

```dotenv
DOMAIN=notes.example.com
DJANGO_SECRET_KEY=replace-with-a-unique-random-secret
```

Replace the hostname and generate a private key with
`python -c 'import secrets; print(secrets.token_urlsafe(64))'`. Save the output only
in the server's environment file or secret store, then restrict the file with
`chmod 600 .env.production`. Keep the key stable across restarts.

```bash
docker compose --env-file .env.production -p notes-production -f compose.production.yml up --build --detach --wait
docker compose --env-file .env.production -p notes-production -f compose.production.yml logs --follow
```

Caddy obtains and renews a certificate once DNS resolves and ports are reachable.
Allow a short delay for initial issuance, then open `https://your-hostname` and
check `/health/`. Do not submit private notes until the browser accepts the certificate.
All subdomains must support HTTPS because HSTS includes subdomains.

Create an administrator:

```bash
docker compose --env-file .env.production -p notes-production -f compose.production.yml exec web python manage.py createsuperuser
```

The app performs deployment checks, migrations, and static collection before
starting Gunicorn. The web container has no published port and sits on an internal
network. Only Caddy accepts public traffic. Caddy overwrites client IP and protocol
headers so HTTPS detection, CSRF, and per-client login limits work behind the proxy.
Never enable `DJANGO_TRUST_PROXY_HEADERS` on a directly accessible app server, and
do not attach untrusted containers to the backend network. If another proxy or CDN
is added in front of Caddy, configure its trusted client-IP handling explicitly.

## Data and upgrades

The `notes-production` project stores SQLite in `notes-production_notes-data` and
certificates in `notes-production_caddy-data`. Keep the same project name across
deployments. Development and production have separate databases by default.

Before upgrading, stop writes and copy a consistent database backup:

```bash
docker compose --env-file .env.production -p notes-production -f compose.production.yml stop web
docker compose --env-file .env.production -p notes-production -f compose.production.yml cp web:/data/db.sqlite3 ./notes-backup.sqlite3
```

Store the backup privately outside the checkout. With the app stopped, copy a
backup back to `web:/data/db.sqlite3` to restore it, then ensure `/data` belongs
to UID/GID `10001` before restarting. Test restores before relying on backups.
Schema changes may require restoring both the previous image and its matching
database backup when rolling back.

After pulling and reviewing updates:

```bash
docker compose --env-file .env.production -p notes-production -f compose.production.yml up --build --detach --wait
```

Existing root-owned volumes need a one-time ownership update while the app is stopped:

```bash
docker compose --env-file .env.production -p notes-production -f compose.production.yml run --rm --no-deps --user root --cap-add CHOWN web chown -R 10001:10001 /data
```

Use `down` to stop the stack while preserving volumes. Do not add `--volumes`
unless you intend to delete notes and certificates. Schedule protected backups
and monitor disk space, `/health/`, and application logs on the deployment host.

## Local production check

```bash
python scripts/test_production.py
```

This builds a separate test stack, uses Caddy's local certificate authority for
`localhost`, and verifies HTTPS without disabling certificate validation. It
checks static files, redirects, secure cookies, CSRF, header spoofing, private
note creation, and upload limits, then deletes only its test project and data.

The supplied stack has been tested locally; a public deployment still needs real
DNS, server access, and a final certificate/reachability check.

Configuration references: [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[Caddy request limits](https://caddyserver.com/docs/caddyfile/directives/request_body),
and [Gunicorn settings](https://gunicorn.org/reference/settings/).
