# ADR 0005: Technology stack and code conventions

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The tool is small, single-user and edited by agents. The discogs repository it wraps is Python with `uv`; its ADR 0001 (`docs/adr/0001-general-python-rules.md` in that repository) conventions (tabs, single quotes) are the owner's style.

## Decision

- **Backend**: one file, `app.py`, FastAPI + uvicorn, run as a `uv` script with PEP 723 inline dependencies (`fastapi`, `uvicorn`, `mutagen`, `python-slugify`, `unidecode`, `pathvalidate`, `pillow`) and the shebang `#!/usr/bin/env -S uv run`. No database, no ORM, no background service besides the job thread ([0008](0008-job-model.md)).
- **FLAC access**: `mutagen`. Tag keys are written in UPPERCASE; keys with spaces are read as fallbacks only (`ACOUSTID FINGERPRINT`, `MUSICBRAINZ ALBUM ID`, `CATALOG NUMBER`) and written with underscores. The legacy spaced dynamic-range keys (`DYNAMIC RANGE`, `ALBUM DYNAMIC RANGE`) are not read at all; only `DYNAMIC_RANGE` and `ALBUM_DR` count.
- **Discogs access**: plain HTTPS with `urllib` against `api.discogs.com` (no client library), user agent `Tagwright/<version>`, `Authorization: Discogs token=...` ([0013](0013-discogs-track-assignment.md)).
- **Frontend**: one file, `index.html`, vanilla JavaScript, no framework, no bundler for JS. Styling is Tailwind CSS v4 + daisyUI 5 with the custom theme `fixer` ([0017](0017-ui-layout-and-design-system.md)).
- **CSS build**: sources in `ui/` (`app.in.css`, `package.json`). `cd ui && npm install && npm run build` scans `index.html` for classes and writes `static/app.css`, which **is committed** so the Docker image needs no Node. Every change that adds a Tailwind/daisyUI class to `index.html` rebuilds and commits `static/app.css`. A class that does not appear in the built CSS does nothing (this bit us: `max-w-3xl` was missing, so arbitrary values such as `max-w-[48rem]` are used for dialog widths).
- **Static assets are local** (`static/`): Discogs and MusicBrainz icons are committed, not fetched at runtime. Known exception: the Inter font loads from Google Fonts.
- **Style**: tabs for indentation, single quotes for string literals, docstrings state the contract, comments explain why. Match the existing code before introducing a new pattern.
- **Errors**: `HTTPException` with a plain-language `detail`; the UI shows it in a toast or the dialog's error line. Unreadable albums degrade to a `needs` row with an `error` field instead of failing the list.

## Consequences

- Single files stay readable only while small; if `app.py` outgrows a single screen of concerns, split by ADR, not by habit.
- No test framework is in place ([0018](0018-verification.md)).
