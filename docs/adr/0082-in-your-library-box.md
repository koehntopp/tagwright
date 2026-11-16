# ADR 0082: "In your library" lists the other versions of an album's Discogs master

- **Status**: Accepted
- **Date**: 2026-11-16

## Context

One record often exists in the library in several pressings (the 1982 CD and a 2016 remaster). Before assigning or moving an album the owner wants to see which versions are already there, without searching the library by hand. The Discogs master release ties the pressings together; every Discogs assignment writes it as `DISCOGS_MASTER_ID` (`m<number>`, [0013](0013-discogs-track-assignment.md)).

## Decision

- **A box "In your library"** in the inspector, below the "New folder" line: one line per **other** version of the album's Discogs master in the library, each the album title followed by its version string (`ALBUM` and `VERSION`, for example `Hello, I Must Be Going! 1982 DR14 CD (299 263-2)`; the version is left out when `ALBUM` already holds it). The lines are text, nothing to click; the full path is the hover text. The box is shown in the Staging and in the Library view alike; in the library an album does not list itself. With no other version the box is not shown.
- **Match: the Discogs master only.** An album without a Discogs release ID, or whose release has no master, shows no box. There is no guess by artist and title.
- **`GET /api/library/versions?path=`** returns `{master, versions: [{path, artist, album, version}]}`, sorted by folder path. It reads the stored summaries ([0067](0067-stored-album-summaries.md)) of the albums the watcher's index lists, so it touches no file of the library; an album whose summary is not stored yet is not listed until it is. Read-only, so the 409 rule does not apply ([0008](0008-job-model.md)); `path` goes through `safe()` ([0007](0007-trust-boundary-and-secrets.md)).
- The summary gets `master` (the digits of `DISCOGS_MASTER_ID`, empty when there is none); `SUMMARY_VERSION` is 4, so the stored summaries are read again once in the background after the update ([0067](0067-stored-album-summaries.md)).
- Use case UC-17 of [0002](0002-purpose-scope-and-use-cases.md).

## Consequences

- The box lags the library by the summary pass; a version moved in by the watcher shows after its summary is stored.
- Versions the owner tagged with a different master (or none) are not found; fixing that is a Discogs assignment, not a setting.
- Tests: `tests/test_library_versions.py` (master in the summary, other versions listed, the album does not list itself, no master lists nothing).
