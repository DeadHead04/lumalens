# Changelog

## 0.1.0 — 2026-10-30

Initial public release:

- API-first discovery for supported Luma cities with timezone-aware date filters.
- Saved-session login through an isolated Chrome window.
- Cookie imports from Playwright, JSON, Netscape files, and optional Chrome profiles.
- Past/upcoming account history and visible event guest lists.
- Paginated retrieval with deduplication, completeness metadata, retries, and rate-limit handling.
- JSON/CSV exports with private file modes on POSIX and CSV formula escaping.
- Cross-platform setup docs, runnable examples, offline regression tests, and GitHub Actions CI.
- Bundled timezone data dependency for Windows and systems without an IANA timezone database.

Known limits: no arbitrary-city coverage or past city discovery; guest access depends on Luma permissions; direct Chrome decryption depends on OS protections. Live workflows were tested on macOS; offline CI covers additional platforms. Unofficial API compatibility can change.
