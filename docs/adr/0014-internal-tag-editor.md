# ADR 0014: Internal tag editor; what is editable and what is Discogs-owned

- **Status**: Accepted
- **Date**: 2026-11-08
- **Supersedes**: the earlier external-editor link (a `yate://` URL built from a client-side path mapping), removed

## Context

UC-7. The first design opened a desktop tagger through a URL with a path translated from the server to the client. That needs per-client configuration and does not work from a phone or a second computer. The discogs repository defines who owns which tag (its ADR 0002 and `CLAUDE.md`): **user-set tags lead and are never overwritten by automation; every other tag `fixtags` writes comes from Discogs and is overwritten on each run.**

## Decision

The **Tag Editor** button (dark `btn-neutral`, left of Run fixes) opens one dialog with three tabs: **Album**, **Tracks**, **Discogs / Musicbrainz**.

### Album tab: tags the pipeline never overwrites
Written to every file of the album; an emptied field removes the tag. Field labels and order (two columns, then three, then two):

1. **Album Artist Override**, **Album Title Override**: empty unless the override tag is really set (`GET /api/tags` no longer falls back to `ALBUMARTIST` / `ALBUM` for them), without help text. When the album has a Discogs release, small print under each shows what Discogs says: `ALBUM ARTIST: <ALBUMARTIST tag>` (the artist currently written, which is the Discogs artist unless an override is set) and `ALBUM TITLE: <ALBUM_MASTER_TITLE, else ALBUM_RELEASE_TITLE>`.
2. **Album Format**, **Album Edition**.
3. **Catalog #** (editable), **Year Release** and **Year Master Release** (read-only, from `ALBUM_RELEASE_YEAR` and `ALBUM_MASTER_YEAR`; Discogs-owned, so never editable).
4. **Discogs Release ID** (read-only: the ID badge with its icon and link, the same as in the inspector but with the full ID, followed by a pen that opens the release dialog) and **Musicbrainz Release ID** (`MUSICBRAINZ_ALBUMID`, the same badge and pen; the ID is set only through the MusicBrainz dialog, which also accepts a pasted ID, so it is no longer typed in this tab). There are no help texts under the two ID fields and no separate release bars below.

| Tag | Meaning |
|-----|---------|
| `ALBUM_ARTIST_OVERRIDE` | also written to `ALBUMARTIST` immediately; clearing restores the Discogs artist (see below) |
| `ALBUM_TITLE_OVERRIDE` | also written to `ALBUM` immediately; clearing restores the Discogs master title (see below) |
| `ALBUM_FORMAT` | for example CD, SACD, Vinyl; filled from the Discogs release by the assignment when empty ([0053](0053-discogs-search-and-assignment-consolidated.md)); **must not be empty** (otherwise `fixtags.py` would silently assume CD) |
| `ALBUM_EDITION` | part of the version string; a changed value refreshes the Discogs tags at once, which rewrites `VERSION` ([0054](0054-album-status-and-steps-consolidated.md)) |
| `CATALOGNUMBER` | part of the version string; **must not be empty** (enter `none` if the release has none, as Discogs does); alternative spellings are removed when it is changed |
| `MUSICBRAINZ_ALBUMID` | anchors language tags; set through the MusicBrainz dialog ([0023](0023-musicbrainz-release-search.md)), not typed here |

The Discogs release dialog is [0053](0053-discogs-search-and-assignment-consolidated.md), the MusicBrainz one [0023](0023-musicbrainz-release-search.md). The Discogs ID itself is changed only through its dialog. The `SUBTITLE` tag (a format fallback in `fixtags.py`) is deliberately not editable here; existing values stay untouched and still apply.

The pencils next to the album artist and the album title in the inspector header open a small dialog for the two override fields; both write the same tags through the same code.

### Clearing an override restores the Discogs value
`ALBUMARTIST` was originally set (by the tagger, from the Discogs data) to the Discogs release artist, and `fixtags.py` touches it only while `ALBUM_ARTIST_OVERRIDE` is set (it never fills it from Discogs). So after an override is cleared the file would keep the override value forever. Therefore, when an override tag that exists is cleared, Tagwright looks the release up on Discogs (the album's `DISCOGS_RELEASE_ID`) and writes the value `fixtags.py` would compute: `ALBUMARTIST` = the release artists (names without the `(n)` suffix, join words kept), `ALBUM` = the master title, or the release title when there is no master (the rule in discogs ADR 0002 §3). The lookup happens before any file is changed; if Discogs cannot be reached or the album has no Discogs ID, an artist/title override is not cleared and the error is shown. Clearing an override that is not set changes nothing, so saving the dialog never overwrites a hand-set `ALBUMARTIST`.

### Tracks tab
One row per file: a drag grip, a selection box, disc, track, title, artist, disc subtitle, and a pen button that opens the lyrics editor ([0015](0015-track-playback-and-track-edit.md)). Only changed rows are sent (compared per file, so reordering is safe).

- **Select**: the box selects a row, shift-click selects the range from the last clicked box (or deselects it when the clicked row was selected), the header box selects all.
- **Bulk edit** (a bar above the table while rows are selected): choose **Disc**, **Disc subtitle**, **Artist** or **Track**, type a value, **Set** writes it into the field of every selected row. **Renumber from n** gives the selected rows the track numbers n, n+1, ... in list order. Nothing is written until Save.
- **Reorder**: drag a row by its grip (when the row is part of the selection, the whole selection moves as a block) onto the row it should go before, or below the last row. The disc and track numbers belong to the **positions**: after a move every row takes the disc and track of the position it now occupies, so a reorder changes the numbering the way the list reads; titles, artists and subtitles move with their rows. Change numbers afterwards with Renumber or by hand if another scheme is wanted. This is client-side only; the save endpoint is unchanged. **`TITLE`, `DISCNUMBER` and `TRACKNUMBER` must not be empty**: the dialog and the server (400, checked before anything is written) refuse a row with an empty one. Writes `TITLE`, `DISCNUMBER`, `TRACKNUMBER`, `ARTIST`, `SET SUBTITLE` and `DISCSUBTITLE` (kept equal so it shows before the next fix). Files are renamed afterwards ([0010](0010-bliss-file-naming.md)).

### Discogs / Musicbrainz tab: read-only
Two sections. **Discogs**: the tags `fixtags.py` writes from the release, shown as key and value and not editable: dates and years, `ALBUM`, `VERSION`, master/release titles and years, `ORIGINAL_TITLE`, `ALBUM_MAX_RESOLUTION`, country, labels, catalogue numbers, format, genres, styles, notes, series, data quality, `ALBUM_DR`, and the families `ALBUM_COMPANY_*`, `ALBUM_CREDIT_*`, `ALBUM_IDENT_*` and `DISCOGS_*` (written by the Discogs assignment, [0053](0053-discogs-search-and-assignment-consolidated.md); `DISCOGS_RELEASE_ID` itself is shown on the Album tab). The player tags the assignment fills when empty (`GENRE`, `LABEL`, `COMPOSER`, ...) are ordinary tags and are not listed here. **MusicBrainz**: the tags the MusicBrainz apply writes ([0023](0023-musicbrainz-release-search.md)) from the first file: every `MUSICBRAINZ*` tag except the release ID (an Album-tab field), plus `BARCODE` and `ASIN`. A note states that the overrides on the Album tab take precedence over `ALBUM` and `ALBUMARTIST`. `GET /api/tags` returns `discogs`, `musicbrainz` and `album_artist` (the `ALBUMARTIST` tag) next to `fields`, `discogs_id` and `tracks`; it is read-only.

### Rules
- The editable list and the read-only list are constants in `app.py` (`ALBUM_FIELDS`, `DISCOGS_FIXED`, `DISCOGS_PREFIXES`) and mirror `fixtags.py` (the `DISCOGS_` prefix is Tagwright's own, from [0053](0053-discogs-search-and-assignment-consolidated.md)). A change to `fixtags.py` that moves a tag between "user input" and "Discogs-derived" requires updating them and this ADR.
- A tag Discogs owns is never made editable here; to change it, change the release or add an override.
- Saves are refused while a job runs ([0008](0008-job-model.md)).

## Consequences

- No per-client setup. Free-form editing of arbitrary tags (composer, genre) is not offered because the pipeline neither writes nor needs them.
