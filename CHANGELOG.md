# Changelog

User-facing changes and maintenance updates are recorded here.

## [Unreleased]

### Added

- Note detail pages, 400-character previews, and 10-note pagination.
- Title/content search, category filtering, and a personal notes list.
- Owner-only editing and POST-only deletion with a confirmation page.
- Shared database limits for public/admin login and registration attempts.
- Regression tests for permissions, text rendering, filters, pagination,
  authentication limits, and author-name migrations.
- Docker build/runtime checks and Python dependency auditing in CI.
- Expanded root security policy.

### Changed

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
