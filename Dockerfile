FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_DATABASE_PATH=/data/db.sqlite3
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh \
    && groupadd --gid 10001 notes \
    && useradd --uid 10001 --gid notes --no-create-home --shell /usr/sbin/nologin notes \
    && mkdir -p /data /app/src/staticfiles \
    && chown notes:notes /data /app/src/staticfiles
COPY src/ ./src/
WORKDIR /app/src
USER notes:notes
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3).close()"
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["serve"]
