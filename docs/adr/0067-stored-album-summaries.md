# ADR 0067: Album summaries are stored, and the library is listed from the index

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: the scan cache of [0054](0054-album-status-and-steps-consolidated.md) (in memory only, checked by stat'ing every file)

## Context

Switching the board to the library took minutes after every restart or redeploy (111 s for 827 albums and 11,397 files on an SMB share) and 2 to 7 s afterwards: the summary of each album needs its tags read, and even a cached one was checked by listing the library and stat'ing every file on every request.

## Decision

- A finished summary is stored in SQLite (`DATA_DIR/summaries.db`, `library/summaries.py`) with its **signature**: the album's files (path inside the album, mtime in nanoseconds, size) and `SUMMARY_VERSION`. A stored summary whose signature still matches is used as it is, so a restart costs nothing. Raising `SUMMARY_VERSION` (when `summarize()` returns something else) reads every album again.
- For an album of the library the signature comes from the **watcher's index** ([0037](0037-library-watcher-and-layout.md)), which already knows every file's mtime and size: no file is touched. The index lists the albums too, so `GET /api/albums` for the library is a database read. Until the watcher has finished a first pass on the library, and for staging, the files are listed and stat'ed as before. The signature string is the same either way.
- A background thread reads the albums whose stored summary is missing or out of date, two at a time, a minute apart, and forgets the rows of albums that are gone. So the library is ready before one switches to it, and a change shows after the watcher's next pass.
- **The board follows the watcher.** When the library reports new activity (files moved, folders removed), the page reloads the album list without the loading skeleton, so an album that the watcher moved to another folder (a corrected artist name) is not left as a card without files. A card whose folder is gone is dropped when it is refreshed, and `GET /api/album` answers 404 for it, not 500.
- `GET /api/albums?fresh=1` ignores the index and the stored signatures and stats the files; the board's refresh button uses it. Edits made in Tagwright drop the album's stored summary at once ([0054](0054-album-status-and-steps-consolidated.md)).

## Consequences

- An external tool that changes tags in place, without touching the folder's mtime, is seen at the watcher's next full sweep (`sweep_hours`, 24 by default), when the refresh button or Re-analyze is used, or when a Tagwright edit refreshes the album. Layout changes and added or removed files are seen at the next quick pass, as before.
- The very first fill of a large library still reads every file once, in the background.
- The summary store is a cache: deleting `summaries.db` costs one refill.
