"""Check the production stack over verified local HTTPS, then remove test data."""

from http.cookiejar import CookieJar
from http.client import HTTPConnection
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, HTTPSHandler, Request

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "--project-name", "notes-production-check", "-f", str(ROOT / "compose.production.yml")]


def main():
    # A distinct project and loopback ports keep this check away from user data.
    env = {**os.environ, "DOMAIN": "localhost", "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
           "BIND_ADDRESS": "127.0.0.1", "HTTP_PORT": "18080", "HTTPS_PORT": "18443"}

    def compose(*args, **kwargs):
        return subprocess.run([*COMPOSE, *args], cwd=ROOT, env=env, check=True, **kwargs)

    try:
        compose("up", "--build", "--detach", "--wait", "--wait-timeout", "120")
        with TemporaryDirectory(prefix="notes-https-") as directory:
            certificate = str(Path(directory) / "root.crt")
            for attempt in range(30):
                try:
                    compose("cp", "proxy:/data/caddy/pki/authorities/local/root.crt", certificate, capture_output=True)
                    break
                except subprocess.CalledProcessError:
                    if attempt == 29:
                        raise
                    time.sleep(1)
            cookies = CookieJar()
            opener = build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=certificate)), HTTPCookieProcessor(cookies))
            origin = "https://localhost:18443"

            def request(path, data=None, headers=None):
                payload = urlencode(data).encode() if data is not None else None
                try:
                    return opener.open(Request(origin + path, data=payload, headers=headers or {}), timeout=10)
                except HTTPError as error:
                    return error

            for attempt in range(30):
                try:
                    with request("/health/") as response:
                        assert response.status == 200
                    break
                except (URLError, ConnectionError):
                    if attempt == 29:
                        raise
                    time.sleep(1)
            for path in ("/", "/login.html", "/static/css/site.css", "/static/vendor/tinymce-7.9.3/tinymce.min.js"):
                with request(path) as response:
                    assert response.status == 200, (path, response.status)
                    assert "max-age=" in response.headers["Strict-Transport-Security"]
                    assert len(response.read()) > 0
            connection = HTTPConnection("localhost", 18080, timeout=10)
            connection.request("GET", "/")
            redirect = connection.getresponse()
            assert redirect.status == 308
            assert redirect.headers["Location"].startswith("https://")
            connection.close()

            with request("/signup.html") as response:
                token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.read().decode()).group(1)
            password = secrets.token_urlsafe(24)
            with request("/signup.html", {"username": "https_test_writer", "password1": password, "password2": password, "csrfmiddlewaretoken": token}, {"Origin": origin}) as response:
                assert response.status == 200
            assert any(cookie.name == "sessionid" and cookie.secure for cookie in cookies)
            assert any(cookie.name == "csrftoken" and cookie.secure for cookie in cookies)
            with request("/post_form.html", {"title": "Rejected", "content": "Missing CSRF"}) as response:
                assert response.status == 403
            with request("/post_form.html") as response:
                token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.read().decode()).group(1)
            with request("/post_form.html", {"title": "HTTPS draft", "content": "Saved through the production proxy.", "visibility": "draft", "csrfmiddlewaretoken": token}, {"Origin": origin, "X-Forwarded-Proto": "http", "X-Real-IP": "forged-client"}) as response:
                assert response.status == 200
                assert b"HTTPS draft" in response.read()
                assert "no-store" in response.headers["Cache-Control"]
            with request("/notes/transfer/", {}, {"Content-Length": str(27 * 1024 * 1024)}) as response:
                assert response.status == 413
            print("Production HTTPS, static files, redirects, secure cookies, CSRF, proxy headers, draft saving, and upload limits passed.")
    except Exception:
        subprocess.run([*COMPOSE, "logs", "--no-color", "--tail", "80"], cwd=ROOT, env=env)
        raise
    finally:
        # These volumes belong exclusively to the isolated test project.
        compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
