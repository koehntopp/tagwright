# ADR 0037: The library folder: layout template, watcher, status

- **Status**: Accepted
- **Date**: 2026-11-11
- **Supersedes**: the rule of [0010](0010-bliss-file-naming.md) that Tagwright never renames album folders, **for the output folder only** (the input folder is still never reorganised), and the flat move of [0011](0011-ingestion-move.md) (see "Move to library")

## Context

The owner kept the library tree `<artist>/<album>/<disc>_<track>_<title>.flac` in order with `bliss.py` from the discogs repository, run by hand. With the pipeline inside Tagwright ([0036](0036-standalone-pipeline-package.md)) the last external step is the one that organises the output folder. The owner decided that the output folder **is** the library, that a file without `ALBUMARTIST` has no fallback to `ARTIST` ([0010](0010-bliss-file-naming.md)), and that the watcher applies changes from the start.

## Use cases (added to [0002](0002-purpose-scope-and-use-cases.md))

- **UC-12** Keep the output folder in the canonical layout automatically: new and changed files are moved and renamed after a cooldown.
- **UC-13** Configure that layout in Settings (a Library tab, drag and drop of tag chips) and see what it does to a real album before saving.
- **UC-14** See the library's state at a glance (album artists, albums, tracks, what the watcher is doing, what it could not place) and re-analyse it by hand.

## Decision

- **Language: Python**, as the package `library/` next to `pipeline/`. File names must stay exactly what `pipeline.naming.clean()` (python-slugify, unidecode, pathvalidate) produces, and the work is tag reading and `rename` calls on a share, not computation. A Rust or Go rewrite is reconsidered only if a measured scan is CPU-bound.
- **Layout template** (`library/template.py`): folder levels, an optional disc folder that exists only for multi-disc albums, and the file name; each is a list of chips (a tag with a format, or literal text). Formats: `text` (cleaned), `num` (part before `/`, zero-padded), `int` (leading integer), `year` (first four characters). Palette: album artist, artist, album, version, album + version (the bliss rule), edition, format, catalog number, year, original year, disc, track, title, disc subtitle. A chip may name a fallback tag; none is set by default.
- **The default template is the bliss layout**: `<album artist>/<album [version]>[/Disc <n>]/<disc>_<track>_<title>.flac`. `tests/data/bliss_golden.json` was produced by running the discogs `bliss.py` on 16 albums of tags (umlauts, punctuation, unicode, version already in the album, `1/2` and `DISCTOTAL`, padded discs ...); the planner must give the same paths.
- **Rules of the planner** (`library/planner.py`), from bliss and 0010: an album is multi-disc when a file has `DISCNUMBER` above 1 or a disc total above 1, or when the album folder already has `Disc N` folders; two folder spellings that differ only in case or Unicode form are one folder, the first wins and the other files are skipped (fix the tags); a file is never moved onto an existing name and two files wanting one name do not both move; **a file with an empty tag the template needs is unplaced and stays where it is, with the reason shown. There are no placeholders and no `ARTIST` fallback.**
- **Executor** (`library/executor.py`): case-only changes go through a temporary name; an existing folder that differs only in case is renamed in place; nothing is overwritten or merged; when all FLACs of a folder go to one place the other files in it (cover, `.m3u`, `.cue` ...) go along unless they would overwrite something; a folder that is empty afterwards is removed up to, never including, the root. The only files ever deleted are `.DS_Store`, `._*`, `Thumbs.db` and `desktop.ini` in a folder that would be empty otherwise. (bliss deleted every non-music file in such folders; the library moves them instead.)
- **Index** (`library/index.py`): SQLite `data/library.db` with the directories' mtimes and, per FLAC, (mtime, size) and the tags the layout needs. A file's tags are read only when its (mtime, size) changed.
- **Finding changes without scanning** (`library/scanner.py`): a quick pass stats every known directory and lists only those whose mtime changed. On SMB and NFS there are no change events, but a directory's mtime moves when entries are added, removed or renamed. A tag edited inside a file changes only the file's mtime, so a **full pass** (list and stat everything) runs at start, every 24 hours and on "Re-analyze". Change events on a local disk (inotify) are not used yet; polling is the same on every volume.
- **Cooldown**: a move waits while any file in its source or destination folder changed within the cooldown (default 60 s; file mtime and first-seen time both count). Quick passes run every 120 s, sooner when something waits.
- **Watcher** (`library/watcher.py`): one daemon thread started with the app. Moves hold `Library.exclusive`, which "Move to library" also takes ([0008](0008-job-model.md)). `Apply` off = report only: the status lists the planned moves and nothing changes. Default: on (the owner's decision).
- **Settings** (`settings.json`, key `library`): `apply`, `cooldown`, `interval`, `sweep_hours`, `template`. An invalid template is refused (400) and the watcher shows the error.
- **API**: `GET /api/library` (status), `POST /api/library/rescan`, `POST /api/library/preview` (a template applied to one album of the index, nothing written). Writing endpoints stay under `ROOT`/`INGEST_DIR` ([0007](0007-trust-boundary-and-secrets.md)); the watcher only works below `INGEST_DIR`.
- **Move to library** replaces "Move to ingest" ([0011](0011-ingestion-move.md)): a `fixed` album's FLACs are placed directly at their template paths below the output folder (disc folders as the template says), refused with 409 if any target exists; nothing else of the album folder moves.
- **UI**: the top bar's right zone (still 600 px, [0031](0031-top-bar-again.md)) shows the library status on its left half (a dot, `N artists · N albums · N tracks`, what it does; the dot is red on an error, pulsing blue while scanning or moving, amber while files settle, in report-only mode with planned moves, or when files cannot be placed, green when the library is in order) and the pipeline status ([0030](0030-ui-layout-and-design-system-v2.md)) on its right half. A click opens a dialog (Close, not Cancel) with: recent actions, planned and waiting moves, unplaced files, the **Re-analyze** button. Settings get a **Library** tab: tag chips are dragged into rows (folder levels, disc folder, file name), with per-chip format, a live preview on a real album, validation messages, a reset to the bliss default, and the apply, cooldown and interval settings.

## Consequences

- The first pass on a large library can move many files at once (Apply is on by default). Turn Apply off in the Library tab to see the plan first.
- Files whose tags are incomplete stay put and are listed; fixing the tags (Tag editor, pipeline) places them on the next pass.
- A tag edited inside a library file is noticed at the next full pass (24 h) or on Re-analyze, unless something in its folder changes.
- A changed template re-lays out the whole library at the next full pass.
