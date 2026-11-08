# ADR 0010: Bliss file naming after fixes and edits

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The music server ingests files named in the bliss pattern produced by `bliss.py` in the discogs repository. Names depend on disc number, track number and title, all of which Tagwright's editors can change.

## Decision

- File name: `<disc>_<track>_<title>.flac`. Disc and track are the part of `DISCNUMBER` / `TRACKNUMBER` before any `/`, zero-padded to two digits (defaults `01` and `00`); the title is `clean(TITLE)` (`Unknown Title` if empty).
- `clean(text)` is `sanitize_filename(slugify(text, lowercase=False, separator='_'))`. It is a **copy of `bliss.clean()`** because `bliss.py` imports config and syslog logging; the two must be kept in sync by hand. A change to the rule in the discogs repository requires the same change here.
- `rename_files(album)` renames every FLAC of the album in place (including those in `Disc N` subfolders). It skips a file whose target already exists (unless the two names differ only by Unicode normalisation or case) and logs the skip.
- Renaming runs: after a successful `nzbfix` run; after Discogs track assignment, single-track edit and tag-editor save ([0013](0013-discogs-track-assignment.md), [0014](0014-internal-tag-editor.md), [0015](0015-track-playback-and-track-edit.md)). The Filenames step ([0006](0006-status-model-and-pipeline-steps.md)) is done when every name matches.
- **Album folders are never renamed by Tagwright.** The "New folder" line shows what the library path will be; moving to the ingest folder ([0011](0011-ingestion-move.md)) keeps the folder's current name.

## Consequences

- Duplicate target names (two tracks with the same disc, track and title) leave one file unrenamed and the Filenames step open until fixed.
