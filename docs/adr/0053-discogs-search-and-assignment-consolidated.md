# ADR 0053: Discogs release search and track assignment (consolidated)

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes**: [0013](0013-discogs-track-assignment.md), [0043](0043-assignment-refreshes-the-discogs-tags.md), [0046](0046-discogs-medleys-are-one-release-track.md), [0047](0047-a-real-catalogue-number-replaces-none.md), [0048](0048-reassignment-replaces-what-the-previous-release-filled.md), [0052](0052-discogs-search-by-attributes-and-musicbrainz-match.md). This is the one place that states the current rules; the six ADRs stay as history.

## Context

UC-6. `fixtags` needs a `DISCOGS_RELEASE_ID` and writes only album-level tags; per-track tags come from the ripper or the user. A downloaded album often holds only a subset of the tracks on the Discogs release, so track numbers and totals must follow the album, not the release. Tagwright also replaces the tagger (Yate) that used to import the Discogs data, so the assignment fills what that import wrote.

## Decision

### Search
- `GET /api/discogs/search?q=&path=` searches Discogs releases (`type=release`, 20 results). A numeric query loads that release directly. The dialog shows title, year, country, format, label, catalogue number and thumbnail. The table has a **Year** column of its own and clickable **Year** and **Tracks** headers (first click ascending, next descending, releases without a value last, the header stays visible while the list scrolls; sorting is in the browser). While track counts load, sorting by tracks is applied when the last one arrives.
- The search field **always starts with artist and album**, never with the album's Discogs ID. An album that already has a Discogs ID opens with that release loaded below. Under the field, small print shows the album's artist, album, year and catalog # (when set), each with a copy icon.
- **MusicBrainz match**: when the album has a `MUSICBRAINZ_ALBUMID` and that MusicBrainz release links Discogs releases ([0023](0023-musicbrainz-release-search.md), `discogs_ids`), those results come first with the badge **MusicBrainz match** (`match: 'MusicBrainz'`). MusicBrainz being unreachable only drops the badge. One extra MusicBrainz request per search, cached.
- Search results carry no tracklist, so the track count of each result is fetched separately (`GET /api/discogs/tracks?id=`), three at a time, filling in after the list appears. A failed lookup shows `?`. Parsed releases are cached in memory for the life of the process.

### Rate limiting (copied from the discogs repository)
Same rules as the discogs repository (`fixtags.discogs_fetch`, `find_audiophile_upgrades.py`, discogs ADR 0001 section 6), because the pipeline and the UI share one Discogs key and its limit of 60 requests a minute:
- All Discogs calls go through one lock: **one request at a time, at least 1.1 s apart** (the `min_interval` of `find_audiophile_upgrades.py` and the 1.1 s of `SPEC.md`). When the `X-Discogs-Ratelimit-Remaining` header drops below 3, an extra **5 s** pause follows (also from that script).
- A **429** or an empty/invalid response body is retried up to **3 times after 60 s**. The lock is held during the wait, so concurrent calls pause together instead of bursting afterwards.
- A 404 is not retried (HTTP 404 "not found"); other HTTP errors answer 502; when the retries are exhausted the API answers 429 "Discogs rate limit reached; try again in a minute". A failed request is reported as failed, never as "not found".
- Consequence: the track counts of 20 search results take about 25 s to fill in. Parsed releases are cached, so each release is fetched once per server start.

### Tracklist
- Entries of type `track`, plus **medleys**: an `index` entry with sub-tracks (`CD3-6.1`, `CD3-6.2`, ...) is **one release track** with the entry's title and duration, numbered from the first sub-track's position without the part suffix (`CD3-6.1` is disc 3, track 6); the sub-tracks are not listed. A medley split into separate files stays a manual choice.
- Position `D-T` or `CDD-T` gives disc and track. A plain-number position under a heading `Disc N` / `CD N` / `DVD N` is track T of disc N. Any other position (vinyl `A1`, plain numbers, empty) is numbered sequentially on disc 1.
- Track artists come from the release's per-track artists, else the release artists; the Discogs `(n)` disambiguation suffix is removed.

### Proposed assignment
`POST /api/tracks/propose` scores every file against every release track: title similarity x 0.6, duration closeness (within 8 s, x 0.25, only if Discogs has a duration), same disc and track number x 0.15. Pairs are taken greedily from the highest score; scores below 0.35 stay unassigned.

### Adjusting and applying
- The dialog lists each file with a dropdown of release tracks (or "Skip") and a match/check/skip badge; release tracks not used are listed as "Not in this album". One release track cannot be given to two files (Apply is disabled).
- Disc and track numbers are editable per file. Default: tracks are renumbered `1..n` per disc in release order over the **selected** files, discs renumbered from 1, so a subset has no gaps.
- `POST /api/tracks/apply` writes per assigned file: `DISCOGS_RELEASE_ID`, `TITLE`, `TRACKNUMBER`, `DISCNUMBER`, `TRACKTOTAL` and `TOTALTRACKS` (files on that disc), `DISCTOTAL` and `TOTALDISCS` (distinct discs), and the tags below. Files set to Skip are untouched; the log names every skipped file that carries a Discogs release ID other than the chosen one ("X was skipped and keeps Discogs release A, not B").
- **Then the Discogs tags step** (`pipeline.fixtags.fix_album`, [0036](0036-standalone-pipeline-package.md)) runs on the album, so the card, inspector, folder line and year note show the new release at once; then the files are renamed ([0010](0010-bliss-file-naming.md)). It writes exactly what a run writes (year, original year, album title, version, label, catalogue and the other `ALBUM_*` tags, cover resize), needs three Discogs requests and runs nothing else of the pipeline. A Discogs or MusicBrainz failure does not fail the assignment: the log says "Discogs tags not refreshed: <reason>" and Run fixes does it later. Tags the user owns (overrides, edition) are untouched.

#### Tags filled from the release
Per file, **only when the tag is empty** (an existing value is a user-set tag and is never overwritten), with these exceptions for the release-level tags (catalogue number, `ALBUM_FORMAT`, `ALBUMARTIST`, `ALBUM` and the player tags):
- **Re-assignment**: when a file's `DISCOGS_RELEASE_ID` differs from the release being assigned, Tagwright works out what the **previous** release would have filled (its data, fetched and cached). A tag whose value equals that is replaced by the new release's value; any other value was set by the owner or a tagger and stays. If the previous release cannot be read, nothing is replaced. This works from the file's current ID: once an assignment has overwritten it, the older release is unknown and stale values are edited in the tag editor. Track-level tags (`ARTIST`, `COMPOSER`, `PRODUCER`, `ENGINEER`) stay fill-when-empty.
- **Catalogue number**: Discogs' own `none` is a placeholder. When the release has a real number and a file's catalogue number, under any of its four spellings, is `none` (any case), that tag is removed and the release's number is written.

| Tag | From Discogs |
|-----|--------------|
| `ARTIST` | the track's artists, else the release artists (names without the `(n)` suffix, join words kept) |
| `ALBUMARTIST` | the release artists; skipped when `ALBUM_ARTIST_OVERRIDE` is set |
| `ALBUM_FORMAT` | the release's first format name (`CD`, `SACD`, `Vinyl`, `DVD`, ...), ignoring the wrappers `Box Set` and `All Media`; nothing is written when the release names no format |
| `ALBUM` | the master title, else the release title; skipped when `ALBUM_TITLE_OVERRIDE` is set. `fixtags.py` rewrites `ALBUM` on every run anyway |
| `CATALOGNUMBER` | the first label's catalogue number, **including Discogs' own `none`** (the tag must never be empty); checked under all four spellings (`CATALOGNUMBER`, `CATALOG NUMBER`, `CATALOG_NUMBER`, `CATALOGNO`). The next refresh puts it into `VERSION` |
| cover | the release's primary image, **only when the first file has no embedded picture** ([0016](0016-cover-art.md)) |

**Everything else the old tagger import wrote is imported too** ("import all that are available": the data is in the release anyway). Found by reading the tags of 40 albums in the library that were imported with Yate. Per assigned file, from the release JSON:

*Player tags*, filled **only when empty** (multi-valued where noted):

| Tag | From the release |
|-----|------------------|
| `GENRE` (multi) | genres |
| `MOOD` | styles, joined with `, ` (the tagger's convention) |
| `LABEL` (multi) | label names |
| `MEDIA` | formats, `Name (description,description)`, joined with `, ` |
| `COUNTRY` | country |
| `BARCODE` | the first identifier of type Barcode |
| `CATALOG` (multi) | all label catalogue numbers except `none` |
| `COPYRIGHT` | companies "Phonographic Copyright (p)" as `℗ name` and "Copyright (c)" as `© name`, joined |
| `PUBLISHER` | companies "Published By" |
| `COMPOSER` (multi) | the track's writer credits (Written-By, Composed By, Music By, Songwriter, Lyrics By, Words By), else the release's |
| `PRODUCER`, `ENGINEER` (multi) | the track's producer / engineer credits, else the release's |
| `PERSONNEL` (multi) | every release credit as `Name - Role` |

*Discogs-owned tags*, **replaced on every assignment** (all existing `DISCOGS_*` keys except `DISCOGS_RELEASE_ID` are deleted first, so a changed release leaves no stale links): `DISCOGS_RELEASE_URL`, `DISCOGS_MASTER_ID` (`m<id>`), `DISCOGS_MASTER_URL`, `DISCOGS_ARTIST_URL`, `DISCOGS_ALBUMARTIST_URL`, `DISCOGS_ARTIST_LIST`, `DISCOGS_LABEL_URL` (multi), `DISCOGS_ARTWORK_URL`, `DISCOGS_CATALOG_NUMBER` (`Label: catno`, multi), `DISCOGS_ALBUM_RELEASECOUNTRY`, `DISCOGS_RELEASE_NOTES`, `DISCOGS_VIDEO_URL` (multi, `Title: url`; the old import put the title into the key name, which is not a valid Vorbis key in general), one `DISCOGS_<ROLE>` per company role (`DISCOGS_PRESSED_BY`, `DISCOGS_RECORDED_AT`, `DISCOGS_MIXED_AT`, ...; names joined with `, `; copyright roles are in `COPYRIGHT`), and per track `DISCOGS_RELEASE_ORDINAL_POSITION` (0-based index in the release tracklist) and `TRACK_NUMBER_TEXT` (the Discogs position, for example `1-3` or `A2`). Nothing reads these tags in the discogs scripts; they are kept in the files for players and later use. They overlap with the `ALBUM_*` tags `fixtags.py` writes, which stay as they are.

Not imported, with no Discogs source or not Discogs data: `ARTISTSORT`, `ALBUMARTISTSORT`, `COMMENT` (a ripper note), `DISCOGS_IMPORT_SETTINGS` (the old importer's own state), and the MusicBrainz tags (a separate import, now [0023](0023-musicbrainz-release-search.md); `MUSICBRAINZ_ALBUMID` is user-set).

The result is logged as `filled from Discogs: ...`. A cover that cannot be fetched is logged (`cover not fetched: ...`) and does not fail the assignment. Everything else Discogs-derived (dates, labels, genres, credits, ...) is written by `fixtags.py` on the next Run fixes ([0014](0014-internal-tag-editor.md) "From Discogs"). Not filled, because they are the owner's own tags with no Discogs source: `ALBUM_EDITION`, `SET SUBTITLE`, `MUSICBRAINZ_ALBUMID`.
- Discogs release positions are not stored in a tag, because `fixtags` removes tag families it manages.

### Entry points
"Change release…" / "Choose release…" in the tag editor ([0014](0014-internal-tag-editor.md)) and the Search button on albums that need IDs.

## Consequences

- MusicBrainz tracklists are not supported; MusicBrainz release search is [0023](0023-musicbrainz-release-search.md).
- Requires a Discogs key ([0009](0009-settings-and-api-keys.md)).
