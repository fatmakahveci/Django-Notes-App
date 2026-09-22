"""Record the README demo using synthetic notes in an isolated test database."""

import io
import os
from pathlib import Path
import secrets
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
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from notes.models import Author, Post


class DemoRecording(StaticLiveServerTestCase):
    def test_record_notebook_workflow(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user("demo_writer", password=password)
        author = Author.objects.create(user=user, user_name="Demo writer")
        Post.objects.create(author=author, title="Ideas worth keeping", content="<p>A notebook for small discoveries, unfinished thoughts, and plans for the weekend.</p>")
        Post.objects.create(author=author, title="The weekend list", content="<p>Visit the bookshop. Take a long walk. Try a new recipe.</p>", is_published=False)
        frames, durations = [], []
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("PLAYWRIGHT_CHANNEL"):
                options["channel"] = os.environ["PLAYWRIGHT_CHANNEL"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1120, "height": 1100}, reduced_motion="reduce")

            def capture(duration=2000):
                page.evaluate("document.fonts.ready")
                frame = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
                frames.append(frame.resize((896, 880), Image.Resampling.LANCZOS))
                durations.append(duration)

            page.goto(self.live_server_url + "/login.html")
            page.get_by_label("Username", exact=True).fill("demo_writer")
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Log in", exact=True).click()
            page.goto(self.live_server_url + "/notes/mine/")
            capture()
            page.goto(self.live_server_url + "/post_form.html")
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.get_by_label("Title", exact=True).fill("A quieter morning")
            page.get_by_label("Visibility", exact=True).select_option("draft")
            page.get_by_label("Personal tags", exact=False).fill("routines, ideas")
            page.frame_locator("iframe").locator("body").fill("Leave the phone in another room.\nMake coffee, open a notebook, and write one page before the day gets busy.")
            capture(1500)
            expect(page.locator("[data-save-status]")).to_have_text("Private recovery copy saved", timeout=10000)
            capture()
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_url(self.live_server_url + "/notes/mine/")
            card = page.locator("article").filter(has=page.get_by_role("link", name="A quieter morning", exact=True))
            card.get_by_role("button", name="Pin: A quieter morning", exact=True).click()
            capture()
            page.get_by_role("link", name="A quieter morning", exact=True).click()
            capture()
            page.get_by_role("link", name="Edit note", exact=True).click()
            page.wait_for_function("window.tinymce?.activeEditor?.initialized")
            page.frame_locator("iframe").locator("body").fill("A new version: start with ten minutes of reading, then write one page.")
            page.get_by_role("button", name="Save changes", exact=True).click()
            page.get_by_role("link", name="Version history", exact=True).click()
            capture(2500)
            page.get_by_role("button", name="Restore as draft", exact=False).first.click()
            expect(page.locator("[data-note-body]")).to_contain_text("Leave the phone")
            capture()
            page.get_by_role("link", name="Delete note", exact=True).click()
            page.get_by_role("button", name="Move to Trash", exact=True).click()
            page.get_by_role("link", name="Trash", exact=True).click()
            capture()
            page.get_by_role("button", name="Restore as draft", exact=False).click()
            page.goto(self.live_server_url + "/notes/mine/")
            capture()
            page.get_by_role("link", name="Import / export", exact=True).click()
            capture(2600)
            browser.close()

        destination = ROOT / "docs" / "demo.gif"
        destination.parent.mkdir(exist_ok=True)
        frames[0].save(destination, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
        print(f"Recorded {len(frames)} frames: {destination.relative_to(ROOT)} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    settings.ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
    settings.SECURE_SSL_REDIRECT = False
    raise SystemExit(bool(DiscoverRunner(verbosity=1).run_tests(["__main__"])))
