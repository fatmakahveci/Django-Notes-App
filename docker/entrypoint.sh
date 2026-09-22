#!/bin/sh
set -eu

if [ "${1:-}" = "serve" ]; then
    python manage.py migrate --noinput
    exec python manage.py runserver 0.0.0.0:8000 --noreload
fi

if [ "${1:-}" = "serve-production" ]; then
    python manage.py check --deploy --fail-level WARNING
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    # One synchronous worker avoids concurrent SQLite writes; scale with a
    # server database before increasing worker count.
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
        --workers 1 --timeout 60 --access-logfile - --error-logfile -
fi

# Management commands and CI checks can use the same image without starting HTTP.
exec "$@"
