# TinyMCE 7.9.3

Vendored from the official npm package:
https://registry.npmjs.org/tinymce/-/tinymce-7.9.3.tgz

Package integrity (SHA-512, base64):
`sha512-Mtm54U5YJ6Pyo/GaAx+JSHXTGEuxrg2AowVWCD9zy1eBolp5Ub7S1rTtsyQdxhPegfhLuR3VLiTKGw1tacv09g==`

Only the minified runtime, default icons, DOM model, silver theme, and the
lists/link plugins used by this app are included. CSS is limited to the default
content style and the oxide skin (`skin.min.css` and `content.min.css`), used by
both note forms and Django admin. Unused dark, legacy, inline, and alternate
content skins are omitted. Retained upstream files are unmodified.
The upstream license is in `license.md`, with third-party notices in `notices.txt`;
the app's Apache license does not
replace the licenses of third-party dependencies.

This replaces the vulnerable TinyMCE 7.8.0 bundled with django-tinymce 5.0.0.
Security fixes: https://www.tiny.cloud/docs/tinymce/7/7.9.3-release-notes/

When updating, verify the npm tarball integrity, copy the same runtime assets
and license into a new versioned directory, update TINYMCE_JS_URL, and test
both the note editor and Django admin. Python pip-audit does not scan these
JavaScript files; check TinyMCE's upstream security advisories separately.
