"""Exercise the writing workflow against an isolated Django test database."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test.runner import DiscoverRunner
from playwright.sync_api import expect, sync_playwright

from notes.models import Category, Post


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

    def test_recovery_collection_tools_and_accessibility(self):
        User.objects.create_user("notebook_browser", password="Browser-test-only-832!")
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + "/")
            page.keyboard.press("Tab")
            expect(page.get_by_role("link", name="Skip to content")).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.locator("#main-content")).to_be_focused()
            page.goto(self.live_server_url + "/login.html")
            page.get_by_label("Username", exact=True).fill("notebook_browser")
            page.get_by_label("Password", exact=True).fill("Browser-test-only-832!")
            page.get_by_role("button", name="Log in", exact=True).click()
            page.goto(self.live_server_url + "/post_form.html")
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.get_by_label("Title", exact=True).fill("Recovered writing")
            page.get_by_label("Personal tags", exact=False).fill("project, ideas")
            page.frame_locator("iframe").locator("body").fill("Words worth keeping")
            expect(page.locator("[data-save-status]")).to_have_text("Private recovery copy saved", timeout=10000)
            page.once("dialog", lambda dialog: dialog.accept())
            page.reload()
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            expect(page.get_by_label("Title", exact=True)).to_have_value("Recovered writing")
            expect(page.get_by_label("Visibility", exact=True)).to_have_value("draft")
            expect(page.get_by_label("Personal tags", exact=False)).to_have_value("project, ideas")
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            page.get_by_role("button", name="Pin: Recovered writing", exact=True).click()
            expect(page.get_by_role("button", name="Unpin: Recovered writing", exact=True)).to_have_attribute("aria-pressed", "true")
            page.locator("summary").filter(has_text="Bulk actions").click()
            page.get_by_role("checkbox", name="Select all notes on this page").focus()
            page.keyboard.press("Space")
            expect(page.locator("[data-selection-count]")).to_have_text("1 note selected")
            page.get_by_label("Action", exact=True).select_option("publish")
            page.get_by_role("button", name="Apply to selected notes").click()
            expect(page.get_by_role("heading", name="Publish selected notes?")).to_be_visible()
            page.get_by_role("button", name="Publish notes", exact=True).click()
            page.get_by_role("link", name="Recovered writing", exact=True).click()
            page.get_by_role("link", name="Edit note", exact=True).click()
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.frame_locator("iframe").locator("body").fill("A later version")
            page.get_by_role("button", name="Save changes", exact=True).click()
            page.get_by_role("link", name="Version history", exact=True).click()
            page.get_by_role("button", name="Restore as draft", exact=False).first.click()
            expect(page.locator(".draft-notice")).to_be_visible()
            expect(page.locator("[data-note-body]")).to_contain_text("Words worth keeping")
            page.get_by_role("link", name="Delete note", exact=True).click()
            page.get_by_role("button", name="Move to Trash", exact=True).click()
            page.get_by_role("link", name="Trash", exact=True).click()
            page.get_by_role("button", name="Restore as draft", exact=False).click()
            page.goto(self.live_server_url + "/notes/mine/")
            page.locator("summary").filter(has_text="More filters").click()
            page.get_by_label("Personal tag", exact=True).select_option(label="project")
            page.get_by_role("button", name="Apply", exact=True).click()
            expect(page.locator("article")).to_have_count(1)
            for width in (320, 768, 1280):
                page.set_viewport_size({"width": width, "height": 1000})
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                if os.getenv("BROWSER_SCREENSHOT_DIR"):
                    destination = Path(os.environ["BROWSER_SCREENSHOT_DIR"])
                    destination.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(destination / f"collection-{width}.png"), full_page=True)
            page.get_by_role("link", name="Import / export", exact=True).click()
            with page.expect_download() as result:
                page.get_by_role("link", name="Download backup", exact=True).click()
            archive = Path(result.value.path()).read_bytes()
            page.get_by_label("Markdown or ZIP file").set_input_files({"name": "backup.zip", "mimeType": "application/zip", "buffer": archive})
            page.get_by_role("button", name="Import as drafts", exact=True).click()
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            expect(page.locator("article")).to_have_count(2)
            expect(page.locator(".draft-badge")).to_have_count(2)
            # Every visible native field has an accessible name from an explicit label.
            missing = page.locator("input:not([type=hidden]), select, textarea").evaluate_all("elements => elements.filter(el => el.getClientRects().length && !(el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'))).map(el => el.name)")
            self.assertEqual(missing, [])
            self.assertFalse(errors, errors)
            browser.close()

    def test_failed_autosave_keeps_manual_save_available(self):
        User.objects.create_user("offline_writer", password="Browser-test-only-832!")
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page()
            page.goto(self.live_server_url + "/login.html")
            page.get_by_label("Username", exact=True).fill("offline_writer")
            page.get_by_label("Password", exact=True).fill("Browser-test-only-832!")
            page.get_by_role("button", name="Log in", exact=True).click()
            page.goto(self.live_server_url + "/post_form.html")
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.route("**/notes/autosave/", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":"Unavailable"}'))
            page.get_by_label("Title", exact=True).fill("Manual save still works")
            page.get_by_label("Visibility", exact=True).select_option("draft")
            page.frame_locator("iframe").locator("body").fill("Keep this writing")
            expect(page.locator("[data-save-status]")).to_have_text("Backup failed. Save your note before leaving.", timeout=10000)
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            expect(page.get_by_role("link", name="Manual save still works", exact=True)).to_be_visible()
            browser.close()

    def test_two_tabs_cannot_overwrite_new_note_recovery(self):
        User.objects.create_user("two_tab_writer", password="Browser-test-only-832!")
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            context = browser.new_context()
            first = context.new_page()
            first.goto(self.live_server_url + "/login.html")
            first.get_by_label("Username", exact=True).fill("two_tab_writer")
            first.get_by_label("Password", exact=True).fill("Browser-test-only-832!")
            first.get_by_role("button", name="Log in", exact=True).click()
            first.wait_for_url(self.live_server_url + "/")
            second = context.new_page()
            for page in (first, second):
                page.goto(self.live_server_url + "/post_form.html")
                page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            first.get_by_label("Title", exact=True).fill("Winning recovery")
            first.frame_locator("iframe").locator("body").fill("Keep the first tab's text")
            expect(first.locator("[data-save-status]")).to_have_text("Private recovery copy saved", timeout=10000)
            second.get_by_label("Title", exact=True).fill("Losing tab")
            second.frame_locator("iframe").locator("body").fill("Keep this text in the second tab")
            expect(second.locator("[data-save-status]")).to_contain_text("Another tab saved a newer recovery copy", timeout=10000)
            second.get_by_role("button", name="Save", exact=True).click()
            expect(second.locator("[data-error-summary]")).to_contain_text("Another tab changed the recovery copy")
            expect(second.get_by_label("Title", exact=True)).to_have_value("Losing tab")
            expect(second.locator("[data-error-summary]")).to_be_focused()
            recovered = context.new_page()
            recovered.goto(self.live_server_url + "/post_form.html")
            expect(recovered.get_by_label("Title", exact=True)).to_have_value("Winning recovery")
            expect(recovered.get_by_label("Visibility", exact=True)).to_have_value("draft")
            browser.close()
        self.assertFalse(Post.objects.exists())

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
