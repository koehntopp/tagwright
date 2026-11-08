# ADR 0013: Discogs release search and track assignment

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

UC-6. `fixtags` needs a `DISCOGS_RELEASE_ID` and writes only album-level tags; per-track tags come from the ripper or the user. A downloaded album often holds only a subset of the tracks on the Discogs release, so track numbers and totals must follow the album, not the release.

## Decision

### Search
- `GET /api/discogs/search?q=` searches Discogs releases (`type=release`, 20 results). A numeric query loads that release directly. The dialog shows title, year, country, format, label, catalogue number and thumbnail.
- Search results carry no tracklist, so the track count of each result is fetched separately (`GET /api/discogs/tracks?id=`), three at a time, filling in after the list appears. A failed lookup shows `?`. Parsed releases are cached in memory for the life of the process because Discogs allows 60 requests a minute.
- If the album already has a Discogs ID, the dialog opens on that release.

### Rate limiting (copied from the discogs repository)
Same rules as `fixtags.discogs_fetch` and discogs ADR 0001 section 6, because the pipeline and the UI share one Discogs key and its limit of 60 requests a minute:
- All Discogs calls go through one lock: **one request at a time, 1 s apart**.
- A **429** or an empty/invalid response body is retried up to **3 times after 60 s**. The lock is held during the wait, so concurrent calls pause together instead of bursting afterwards.
- A 404 is not retried (HTTP 404 "not found"); other HTTP errors answer 502; when the retries are exhausted the API answers 429 "Discogs rate limit reached; try again in a minute". A failed request is reported as failed, never as "not found".
- Consequence: the track counts of 20 search results take about 25 s to fill in. Parsed releases are cached, so each release is fetched once per server start.

### Tracklist
Entries of type `track` only (headings and index entries are skipped). Position `D-T` or `CDD-T` gives disc and track; any other position (vinyl `A1`, plain numbers, empty) is numbered sequentially on disc 1. Track artists come from the release's per-track artists, else the release artists; the Discogs `(n)` disambiguation suffix is removed.

### Proposed assignment
`POST /api/tracks/propose` scores every file against every release track: title similarity x 0.6, duration closeness (within 8 s, x 0.25, only if Discogs has a duration), same disc and track number x 0.15. Pairs are taken greedily from the highest score; scores below 0.35 stay unassigned. Titles dominate because Discogs durations are often several seconds off.

### Adjusting and applying
- The dialog lists each file with a dropdown of release tracks (or "Skip") and a match/check/skip badge; release tracks not used are listed as "Not in this album". One release track cannot be given to two files (Apply is disabled).
- Disc and track numbers are editable per file. Default: tracks are renumbered `1..n` per disc in release order over the **selected** files, discs renumbered from 1, so a subset has no gaps.
- `POST /api/tracks/apply` writes per assigned file: `DISCOGS_RELEASE_ID`, `TITLE`, `TRACKNUMBER`, `DISCNUMBER`, `TRACKTOTAL` and `TOTALTRACKS` (files on that disc), `DISCTOTAL` and `TOTALDISCS` (distinct discs). Files set to Skip are untouched. Then files are renamed ([0010](0010-bliss-file-naming.md)).
- **Tags the pipeline treats as user input are filled from the release, when missing.** Tagwright replaces the tagger (Yate) that used to import the Discogs data, and no later pipeline step writes these, so the assignment must. Per file, **only when that tag is empty** (an existing value is a user-set tag and is never overwritten, discogs ADR 0002 sections 1 and 2):

  | Tag | From Discogs |
  |-----|--------------|
  | `ARTIST` | the track's artists, else the release artists (names without the `(n)` suffix, join words kept) |
  | `ALBUMARTIST` | the release artists; skipped when `ALBUM_ARTIST_OVERRIDE` is set (`fixtags.py` writes the override) |
  | `ALBUM` | the master title, else the release title (the rule of discogs ADR 0002 section 3); skipped when `ALBUM_TITLE_OVERRIDE` is set. `fixtags.py` rewrites `ALBUM` on every run anyway |
  | `CATALOGNUMBER` | the first label catalogue number that is not `none`; checked under all four spellings (`CATALOGNUMBER`, `CATALOG NUMBER`, `CATALOG_NUMBER`, `CATALOGNO`). The next fix run puts it into `VERSION` |
  | cover | the release's primary image, **only when the first file has no embedded picture** ([0016](0016-cover-art.md)) |

  The result is logged as `filled from Discogs: ...`. A cover that cannot be fetched is logged (`cover not fetched: ...`) and does not fail the assignment. Everything else Discogs-derived (dates, labels, genres, credits, ...) is written by `fixtags.py` on the next Run fixes ([0014](0014-internal-tag-editor.md) "From Discogs"). Not filled, because they are the owner's own tags with no Discogs source: `ALBUM_FORMAT`, `ALBUM_EDITION`, `SET SUBTITLE`, `MUSICBRAINZ_ALBUMID`.
- Discogs release positions are not stored in a tag, because `fixtags` removes tag families it manages.

### Entry points
"Change release…" / "Choose release…" in the tag editor ([0014](0014-internal-tag-editor.md)) and the Search button on albums that need IDs.

## Consequences

- MusicBrainz tracklists are not supported.
- Requires a Discogs key ([0009](0009-settings-and-api-keys.md)).
