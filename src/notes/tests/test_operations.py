from unittest.mock import patch

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import OperationalError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import include, path, reverse


def fail(request, kind):
    errors = {"bad": SuspiciousOperation, "forbidden": PermissionDenied, "server": OperationalError}
    raise errors[kind]("private-diagnostic-detail")


urlpatterns = [
    path("test-errors/<str:kind>/", fail),
    path("", include("config.urls")),
]


class HealthTests(TestCase):
    def test_health_is_public_read_only_and_not_cached(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("sessionid", response.cookies)
        self.assertEqual(self.client.head(reverse("health")).content, b"")
        with self.assertNumQueries(0):
            self.assertEqual(self.client.post(reverse("health")).status_code, 405)

    def test_unavailable_database_returns_generic_503(self):
        with patch("notes.operations.Post.objects.exists", side_effect=OperationalError("private-diagnostic-detail")):
            with self.assertLogs("notes.operations", level="WARNING"):
                response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotContains(response, "private-diagnostic-detail", status_code=503)


@override_settings(DEBUG=False, ROOT_URLCONF=__name__, SECURE_SSL_REDIRECT=False)
class ErrorPageTests(SimpleTestCase):
    def test_missing_page_uses_custom_template(self):
        response = self.client.get("/missing-note/")
        self.assertContains(response, "We couldn't find that page.", status_code=404)
        self.assertTemplateUsed(response, "404.html")

    def test_error_pages_work_without_database_queries_or_diagnostics(self):
        client = Client(raise_request_exception=False)
        for kind, status in (("bad", 400), ("forbidden", 403), ("server", 500)):
            with self.subTest(status=status):
                response = client.get(f"/test-errors/{kind}/")
                self.assertEqual(response.status_code, status)
                self.assertTemplateUsed(response, f"{status}.html")
                self.assertContains(response, "Return to all notes", status_code=status)
                self.assertNotContains(response, "private-diagnostic-detail", status_code=status)

    def test_csrf_failure_explains_how_to_retry_without_exposing_reason(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("signup"), {})
        self.assertContains(response, "Keep a copy of what you wrote", status_code=403)
        self.assertTemplateUsed(response, "errors/csrf_failure.html")
        self.assertNotContains(response, "CSRF cookie not set", status_code=403)
        self.assertIn("no-store", response["Cache-Control"])
