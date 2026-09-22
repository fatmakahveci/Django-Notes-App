# Changelog

User-facing changes and maintenance updates are recorded here.

## [Unreleased]

### Security

- Prevent caching of private note deletion confirmation pages.
- Reject oversized requests before multipart parsing and cap streamed file data
  before it reaches temporary storage, including requests with multiple files.
- Run Docker as an unprivileged user; drop capabilities and prevent privilege
  escalation in Compose. Document migration of existing volume permissions.
- Add regression coverage for upload limits, CSRF, private response headers,
  and deeply nested autosave input.

### Project layout

- Rename the source root to `src/`, the Django configuration package to `config`,
  and the application package to `notes`, keeping the existing database identity.
- Group regression tests under `src/notes/tests/` and templates by their purpose.
- Move Dockerfile to the repository root and the demo GIF to `docs/`.
- Update installation commands, CI, static references, and deployment paths.

### Added

- A separate production Compose stack with Gunicorn, automatic Caddy HTTPS,
  static serving, isolated proxy trust, and an HTTPS integration check in CI.
- A reproducible demo recording covering recovery, pins, history, Trash, and backups.

- A shared Docker entrypoint with automatic migrations, image-level health checks,
  persistent SQLite storage, and HTTP startup checks in CI.

- Private automatic editor recovery with stale-tab protection.
- Sanitized rich-text reading, with headings, lists, emphasis, and links.
- Trash with draft restoration and confirmed permanent deletion.
- A private history of the last 50 saved versions and draft restoration.
- Personal pins and comma-separated tags, date/tag filters, and search highlights.
- Owner-scoped bulk tagging, visibility changes, and moving notes to Trash.
- Markdown downloads, ZIP collection backups, and atomic draft-only imports.
- Keyboard selection controls, live selection counts, larger touch targets, and
  browser coverage for recovery, collection tools, and accessible navigation.

- Private drafts with owner-only reading/downloads and publication controls.
- Draft filters, sorting options, and clickable category filters.
- Unsaved-change warnings, keyboard saving, word counts, and form error summaries.
- Plain-text downloads, clipboard copying, and a print-friendly note layout.
- Browser workflow regression tests in CI and feed query-budget coverage.
- Database readiness endpoint and a Docker Compose health check.
- Custom 400, 403, 404, 500, and CSRF error pages with recovery guidance.
- A shared local/CI verification script with an optional dependency audit.
- Note detail pages, 400-character previews, and 10-note pagination.
- Title/content search, category filtering, and a personal notes list.
- Owner-only editing and POST-only deletion with a confirmation page.
- Shared database limits for public/admin login and registration attempts.
- Regression tests for permissions, text rendering, filters, pagination,
  authentication limits, and author-name migrations.
- Docker build/runtime checks and Python dependency auditing in CI.
- Expanded root security policy.

### Changed

- Consolidate application dependencies in the root requirements file and align
  Docker, Dependabot, and audits with the development/browser dependency groups.
- Split the desktop editor into writing and settings panels, keep save controls
  visible, and refine mobile filters and draft navigation.
- Clarify contributor checks, configuration examples, and repository formatting.
- Exclude local data, environments, caches, and build outputs from Git and Docker.
- Redesign the interface with responsive note cards, clearer filters, dedicated
  reading and form layouts, and a footer that stays below short pages.
- Replace category multi-selects with accessible checkboxes and simplify the
  editor toolbar; add active navigation states and keyboard focus styling.
- Standardize forms, help text, errors, and action links.
- Align Bootstrap CSS and JavaScript on 5.3.8 with verified integrity hashes.
- Upgrade Django to 6.1.1; require Python 3.12 or newer.
- Update setup, usage, migration, security, and contribution documentation.

### Fixed

- Keep note search text aligned with persisted fields during partial saves,
  including when `update_fields` is supplied as an iterator.
- Normalize Unicode usernames before counting login attempts, preventing
  equivalent spellings from bypassing the shared public/admin limit.
- Serve patched TinyMCE 7.9.3 assets in note forms and Django admin, replacing
  the vulnerable 7.8.0 bundled with django-tinymce. Remove unused editor endpoints.
- Search visible text across HTML formatting, character entities, and Unicode
  case differences; backfill existing notes and refresh search text on save.
- Preserve paragraph breaks and decode character entities while escaping HTML.
- Allow category-free posts in the public form and Django admin.
- Restore previously truncated author names when they match linked usernames;
  preserve custom author names.
- Reject notes containing only empty markup or invisible whitespace.
- Remove horizontal overflow and widen the editor on mobile screens.

### Removed

- Unused TinyMCE skins; retain the default styles used by note forms and admin.
- Personal footer credit, identifying profile links, and the old demo GIF
  containing the credit.
- Machine-specific Python environment links from `my_site/bin/`.
- Unused Django REST Framework and CORS dependencies.
- Unused logout template, header image, and house icon.
- Conflicting GPL license file; retain Apache-2.0 in `LICENSE.md`.
