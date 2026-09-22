from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


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
