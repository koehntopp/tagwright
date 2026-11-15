# ADR 0077: The library as CSV for other programs

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

The owner's discogs web app (`/Users/koehntopp/src/discogs`, its own repository) chose releases from an `albums.csv` that `album_list.py` builds by hand ("Refresh") from the files of the library folder. Tagwright keeps the same facts current and stored ([0067](0067-stored-album-summaries.md)), so the other program can read them from Tagwright and the manual export goes away. This is use case UC-16 of [0002](0002-purpose-scope-and-use-cases.md).

## Decision

- **`GET /api/library/albums.csv`** returns every album of the **library** folder (the staging folder is not listed) as CSV: UTF-8, `\n` line ends, one header row, rows sorted by folder path, `Content-Type: text/csv; charset=utf-8`. It is read-only, so the 409 rule for writes ([0008](0008-job-model.md)) does not apply, and it reads no audio file: it is built from the stored album summaries ([0067](0067-stored-album-summaries.md)).
- **Columns**, in this order: `Album Artist`, `Album`, `Version`, `DR`, `Format`, `Edition`, `Original Title`, `Original Date`, `Release Date`, `Catalog Number`, `Discogs Release ID`, `MusicBrainz Album ID`, `Subtitle` (the columns of the discogs repository's `albums.csv`, from the tags of the album's first file), then `Cover Art` (`WIDTHxHEIGHT` of the embedded cover, empty without one), `_DIRECTORY_PATH` and `Directory` (both the album folder).
- **Album** is the title override (`ALBUM_TITLE_OVERRIDE`), else the master title, else the original title, else `ALBUM` without a trailing `[...]`. **Version** is `VERSION`, else `SUBTITLE`. **Catalog Number** is the first non-empty catalogue key ([0047](0047-a-real-catalogue-number-replaces-none.md)).
- **`?path_prefix=`** replaces the library folder at the start of `_DIRECTORY_PATH` and `Directory`, for a client that sees the same files under another path (for example `/Volumes/flac` on the Mac for `/library` in the container). Without it the paths are those inside Tagwright.
- The summary gets an `export` object with these values (`album_export()` in `app.py`); because `summarize()` now returns more, `SUMMARY_VERSION` is 2 and every stored summary is read again once in the background after the update. The first request after such an update can therefore take about 30 seconds; later ones are fast.
- No authentication, like every other endpoint ([0007](0007-trust-boundary-and-secrets.md)); no API key or secret is in the output. The endpoint reads nothing outside the library folder.

## Consequences

- The discogs web app reads this URL (setting `tagwright_url`, refresh interval default 5 minutes; its own ADR 0011) instead of `albums.csv`. `album_list.py` and the scripts that read `albums.csv` stay for command-line use.
- The list lags a reprocess in the library by the library watcher's pass (cooldown and check interval, [0037](0037-library-watcher-and-layout.md)).
- Changing a column or its order changes what other programs read; it needs an ADR change.
- Tests: `tests/test_library_export.py` (header, row values, album title rules, `path_prefix`, staging not listed).
