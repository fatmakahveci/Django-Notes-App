"""Exercise the writing workflow against an isolated Django test database."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "my_site"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_site.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test.runner import DiscoverRunner
from playwright.sync_api import expect, sync_playwright

from blog_app.models import Category, Post


class WritingBrowserTests(StaticLiveServerTestCase):
    def test_draft_to_public_note_and_editor_tools(self):
        # Synthetic data exists only in Django's temporary test database.
        User.objects.create_user("browser_writer", password="Browser-test-only-832!")
        Category.objects.create(title="Ideas")
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + "/login.html")
            page.get_by_label("Username", exact=True).fill("browser_writer")
            page.get_by_label("Password", exact=True).fill("Browser-test-only-832!")
            page.get_by_role("button", name="Log in", exact=True).click()
            page.wait_for_url(self.live_server_url + "/")
            page.goto(self.live_server_url + "/post_form.html")
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            expect(page.locator("[data-save-status]")).to_have_text("No unsaved changes")
            page.get_by_label("Title", exact=True).fill("An idea in progress")
            editor_body = page.frame_locator("iframe").locator("body")
            editor_body.fill("A useful first thought")
            expect(page.locator("[data-word-count]")).to_have_text("4 words")
            page.get_by_label("Visibility", exact=True).select_option("draft")
            page.get_by_role("checkbox", name="Ideas", exact=True).check()
            expect(page.locator("[data-save-status]")).to_have_text("Unsaved changes")
            dialogs = []

            def keep_writing(dialog):
                dialogs.append(dialog.type)
                dialog.dismiss()

            page.once("dialog", keep_writing)
            page.get_by_role("link", name="Cancel", exact=True).click(no_wait_after=True)
            expect(page.get_by_label("Title", exact=True)).to_have_value("An idea in progress")
            self.assertEqual(dialogs, ["beforeunload"])
            for width in (320, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                editor_body.focus()
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                if os.getenv("BROWSER_SCREENSHOT_DIR"):
                    destination = Path(os.environ["BROWSER_SCREENSHOT_DIR"])
                    destination.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(destination / f"editor-{width}.png"), full_page=True)
            editor_body.press("Control+Enter")
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            tabs = page.get_by_role("navigation", name="Note visibility")
            tabs.get_by_role("link", name="Drafts", exact=True).click()
            expect(page.locator("article")).to_have_count(1)
            tabs.get_by_role("link", name="Published", exact=True).click()
            expect(page.get_by_role("heading", name="No notes match your filters.")).to_be_visible()
            tabs.get_by_role("link", name="All my notes", exact=True).click()
            page.get_by_role("link", name="An idea in progress", exact=True).click()
            detail_url = page.url
            self.assertIn("visible only to you", page.locator(".draft-notice").inner_text())
            visitor = browser.new_context()
            response = visitor.request.get(detail_url)
            self.assertEqual(response.status, 404)
            with page.expect_download() as result:
                page.get_by_role("link", name="Download .txt", exact=True).click()
            download = result.value
            self.assertTrue(download.suggested_filename.endswith(".txt"))
            self.assertIn("A useful first thought", Path(download.path()).read_text())
            clipboard_stub = "window.__copied = ''; Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => { window.__copied = text; }}, configurable: true});"
            page.add_init_script(clipboard_stub)
            page.reload()
            page.get_by_role("button", name="Copy text", exact=True).click()
            expect(page.locator("[data-copy-status]")).to_have_text("Note text copied.")
            self.assertEqual(page.evaluate("window.__copied"), "A useful first thought")
            page.evaluate("() => { navigator.clipboard.writeText = async () => { throw new Error('Permission denied'); }; }")
            page.get_by_role("button", name="Copy text", exact=True).click()
            expect(page.locator("[data-copy-status]")).to_contain_text("Copy isn't available")
            page.emulate_media(media="print")
            expect(page.locator(".site-header")).not_to_be_visible()
            expect(page.locator(".note-tools")).not_to_be_visible()
            expect(page.locator(".note-body")).to_be_visible()
            page.emulate_media(media="screen")
            page.get_by_role("link", name="Edit note", exact=True).click()
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.get_by_label("Visibility", exact=True).select_option("published")
            page.get_by_role("button", name="Save changes", exact=True).click()
            page.wait_for_url(detail_url)
            self.assertEqual(visitor.request.get(detail_url).status, 200)
            page.goto(self.live_server_url + "/?sort=title")
            expect(page.get_by_label("Sort by", exact=True)).to_have_value("title")
            page.get_by_role("link", name="Filter by Ideas", exact=True).click()
            self.assertIn("sort=title", page.url)
            self.assertIn("category=", page.url)
            for width in (320, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
            page.goto(self.live_server_url + "/post_form.html")
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.get_by_label("Title", exact=True).fill("Preserve this title")
            page.frame_locator("iframe").locator("body").fill("\u00a0")
            page.get_by_role("button", name="Save", exact=True).click()
            expect(page.locator("[data-error-summary]")).to_be_focused()
            expect(page.get_by_label("Title", exact=True)).to_have_value("Preserve this title")
            expect(page.locator("[data-save-status]")).to_have_text("Unsaved changes")
            self.assertFalse(errors, errors)
            context.close()
            visitor.close()
            browser.close()
        note = Post.objects.get(title="An idea in progress")
        self.assertTrue(note.is_published)
        self.assertEqual(note.categories.get().title, "Ideas")
        self.assertEqual(Post.objects.count(), 1)

    def test_draft_form_and_download_work_without_javascript(self):
        User.objects.create_user("no_js_writer", password="Browser-test-only-832!")
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(java_script_enabled=False)
            page = context.new_page()
            page.goto(self.live_server_url + "/login.html")
            page.get_by_label("Username", exact=True).fill("no_js_writer")
            page.get_by_label("Password", exact=True).fill("Browser-test-only-832!")
            page.get_by_role("button", name="Log in", exact=True).click()
            page.wait_for_url(self.live_server_url + "/")
            page.goto(self.live_server_url + "/post_form.html")
            page.get_by_label("Title", exact=True).fill("Writing without JavaScript")
            page.get_by_label("Content", exact=True).fill("A plain-text draft.")
            page.get_by_label("Visibility", exact=True).select_option("draft")
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            page.get_by_role("link", name="Writing without JavaScript", exact=True).click()
            expect(page.locator(".draft-notice")).to_be_visible()
            with page.expect_download() as result:
                page.get_by_role("link", name="Download .txt", exact=True).click()
            self.assertIn("A plain-text draft.", Path(result.value.path()).read_text())
            context.close()
            browser.close()
        self.assertFalse(Post.objects.get(title="Writing without JavaScript").is_published)


if __name__ == "__main__":
    settings.ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
    settings.SECURE_SSL_REDIRECT = False
    raise SystemExit(bool(DiscoverRunner(verbosity=2).run_tests(["__main__"])))
