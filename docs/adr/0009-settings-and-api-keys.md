# ADR 0009: Settings and API keys

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

Folders and API keys must be changeable from the UI without editing environment variables or the discogs repository.

## Decision

- Settings (UC-1): input folder, output folder, **minimum cover size in pixels** (`min_cover`, default 1400, 0 = off; [0016](0016-cover-art.md)), Discogs API key, lrclib.net API key. Dialog opened by the Settings entry at the bottom of the sidebar.
- Precedence: values saved in `DATA_DIR/settings.json` override the environment (`ROOT`, `INGEST_DIR`). The input folder must exist and both folders must be absolute paths (`~` expanded). Saving clears the scan cache and is refused while a job runs.
- Keys: a blank field keeps the stored key; `clear_<key>: true` removes it. The API returns only a hint of the last four characters.
- **Config overlay**: when a key is stored, the app writes `DATA_DIR/overlay/config.py` (mode 0600) as a copy of the discogs `config.py` plus `discogs_api_key = ...` / `lrclib_api_key = ...`, and starts `nzbfix.py` with `CONFIG_DIR` pointing at it. `log.py` in the discogs repo puts `CONFIG_DIR` first on `sys.path`, so the overlay wins and the original `config.py` stays untouched. With no stored key, no overlay is made.
- The track editor ([0013](0013-discogs-track-assignment.md)) uses the stored Discogs key, falling back to `discogs_api_key` in `config.py` under `CONFIG_DIR` or `DISCOGS_DIR`.
- Settings that only concern the browser (none today) would live in `localStorage`; the old local-path mapping and editor link template were removed ([0014](0014-internal-tag-editor.md)).

## Consequences

- The lrclib key is stored and passed on, but no discogs script reads it yet (`lrclib_client.py` sends only the public app id). Using it needs a change in the discogs repository.
