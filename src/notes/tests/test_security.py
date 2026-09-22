from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse

from ..models import Author, NoteRecovery, Post
from ..middleware import TrustedProxyMiddleware


class TrustedProxyTests(SimpleTestCase):
    @override_settings(TRUST_PROXY_HEADERS=False)
    def test_forwarded_client_address_is_ignored_by_default(self):
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_REAL_IP="192.0.2.2")
        TrustedProxyMiddleware(lambda request: None).process_request(request)
        self.assertEqual(request.META["REMOTE_ADDR"], "192.0.2.1")

    @override_settings(TRUST_PROXY_HEADERS=True)
    def test_isolated_proxy_address_drives_authentication_limits(self):
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_REAL_IP="2001:db8::1")
        TrustedProxyMiddleware(lambda request: None).process_request(request)
        self.assertEqual(request.META["REMOTE_ADDR"], "2001:db8::1")

    @override_settings(TRUST_PROXY_HEADERS=True)
    def test_invalid_proxy_addresses_are_rejected(self):
        request = RequestFactory().get("/", HTTP_X_REAL_IP="192.0.2.1, 192.0.2.2")
        with self.assertRaises(SuspiciousOperation):
            TrustedProxyMiddleware(lambda request: None).process_request(request)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    AUTH_ATTEMPT_LIMITS={"login": [("username", 2, 600)], "signup": []},
)
class AuthenticationNormalizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "writer", password="correct-password", is_staff=True,
        )

    def test_unicode_aliases_cannot_bypass_shared_login_limit(self):
        for name in ("login", "admin:login"):
            self.client.post(reverse(name), {"username": "writer", "password": "wrong"})
        for name in ("login", "admin:login"):
            for username in ("ｗｒｉｔｅｒ", "𝘸𝘳𝘪𝘵𝘦𝘳"):
                with self.subTest(endpoint=name, username=username):
                    response = self.client.post(reverse(name), {
                        "username": username, "password": "correct-password",
                    }, REMOTE_ADDR="192.0.2.9")
                    self.assertEqual(response.status_code, 429)
                    self.assertNotIn("_auth_user_id", self.client.session)

    def test_unicode_alias_login_still_works_below_limit(self):
        response = self.client.post(reverse("login"), {
            "username": "ｗｒｉｔｅｒ", "password": "correct-password",
        })
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))


class UnusedEditorEndpointTests(TestCase):
    def test_unused_editor_endpoints_are_not_exposed(self):
        for endpoint in ("compressor", "filebrowser", "flatpages_link_list"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/tinymce/{endpoint}/", {
                    "js": "true", "compress": "false",
                    "plugins": '\");window.untrustedCode=true;//',
                })
                self.assertEqual(response.status_code, 404)


class PrivateRequestSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("private-writer")
        author = Author.objects.create(user=cls.user, user_name="Writer")
        cls.note = Post.objects.create(author=author, title="Confidential draft", content="Text", is_published=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_delete_confirmation_cannot_be_cached(self):
        response = self.client.get(reverse("post-delete", args=[self.note.pk]))
        self.assertContains(response, self.note.title)
        self.assertIn("no-store", response.get("Cache-Control", ""))
        self.assertIn("private", response.get("Cache-Control", ""))

    def test_deeply_nested_autosave_is_rejected_without_losing_recovery(self):
        recovery = NoteRecovery.objects.create(user=self.user, key="new", data={"title": "Keep this"}, version=1)
        response = self.client.post(reverse("note-autosave"), "[" * 5000 + "0" + "]" * 5000, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        recovery.refresh_from_db()
        self.assertEqual(recovery.data, {"title": "Keep this"})
        self.assertEqual(recovery.version, 1)

    @override_settings(NOTE_REQUEST_MAX_BYTES=1024)
    def test_oversized_request_is_rejected_before_upload_parsing_or_csrf(self):
        client = Client(enforce_csrf_checks=True)
        with patch.object(TemporaryFileUploadHandler, "new_file") as temporary_file:
            response = client.post(reverse("transfer-notes"), {"file": SimpleUploadedFile("large.md", b"x" * 2048)})
        self.assertEqual(response.status_code, 413)
        temporary_file.assert_not_called()

    @override_settings(NOTE_UPLOAD_MAX_BYTES=1024, FILE_UPLOAD_MAX_MEMORY_SIZE=0)
    def test_streamed_upload_stops_before_excess_bytes_reach_disk(self):
        written = []
        original = TemporaryFileUploadHandler.receive_data_chunk

        def record_write(handler, chunk, start):
            written.append(len(chunk))
            return original(handler, chunk, start)

        with patch.object(TemporaryFileUploadHandler, "receive_data_chunk", record_write):
            response = self.client.post(reverse("transfer-notes"), {"file": SimpleUploadedFile("large.md", b"x" * 200_000)})
        self.assertEqual(response.status_code, 413)
        self.assertLessEqual(sum(written), 1024)
        self.assertEqual(Post.objects.count(), 1)

    @override_settings(NOTE_UPLOAD_MAX_BYTES=1024)
    def test_upload_limit_counts_all_files_and_rejects_partial_import(self):
        response = self.client.post(reverse("transfer-notes"), {
            "file": SimpleUploadedFile("first.md", b"x" * 600),
            "extra": SimpleUploadedFile("second.md", b"x" * 600),
        })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(Post.objects.count(), 1)

    def test_small_upload_still_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse("transfer-notes"), {"file": SimpleUploadedFile("note.md", b"A note")})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Post.objects.count(), 1)
