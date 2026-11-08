# ADR 0014: Internal tag editor; what is editable and what is Discogs-owned

- **Status**: Accepted
- **Date**: 2026-11-08
- **Supersedes**: the earlier external-editor link (a `yate://` URL built from a client-side path mapping), removed

## Context

UC-7. The first design opened a desktop tagger through a URL with a path translated from the server to the client. That needs per-client configuration and does not work from a phone or a second computer. The discogs repository defines who owns which tag (its ADR 0002 and `CLAUDE.md`): **user-set tags lead and are never overwritten by automation; every other tag `fixtags` writes comes from Discogs and is overwritten on each run.**

## Decision

The **Tag Editor** button (dark `btn-neutral`, left of Run fixes) opens one dialog with three tabs.

### Album tab: tags the pipeline never overwrites
Written to every file of the album; an emptied field removes the tag.

| Tag | Meaning |
|-----|---------|
| `ALBUM_ARTIST_OVERRIDE` | also written to `ALBUMARTIST` immediately; clearing restores the Discogs artist (see below) |
| `ALBUM_TITLE_OVERRIDE` | also written to `ALBUM` immediately; clearing restores the Discogs master title (see below) |
| `ALBUM_FORMAT` | for example CD, SACD (empty: CD) |
| `ALBUM_EDITION` | part of the version string |
| `CATALOGNUMBER` | part of the version string; **must not be empty** (enter `none` if the release has none, as Discogs does); alternative spellings are removed when it is changed |
| `MUSICBRAINZ_ALBUMID` | anchors language tags |

Also shown: the Discogs release ID as a link, with "Change release…" ([0013](0013-discogs-track-assignment.md)). The ID itself is changed only through that dialog. The `SUBTITLE` tag (a format fallback in `fixtags.py`) is deliberately not editable here; existing values stay untouched and still apply.

The pencils next to the album artist and the album title in the inspector header open a small dialog for the two override fields; both write the same tags through the same code.

### Clearing an override restores the Discogs value
`ALBUMARTIST` was originally set (by the tagger, from the Discogs data) to the Discogs release artist, and `fixtags.py` touches it only while `ALBUM_ARTIST_OVERRIDE` is set (it never fills it from Discogs). So after an override is cleared the file would keep the override value forever. Therefore, when an override tag that exists is cleared, Tagwright looks the release up on Discogs (the album's `DISCOGS_RELEASE_ID`) and writes the value `fixtags.py` would compute: `ALBUMARTIST` = the release artists (names without the `(n)` suffix, join words kept), `ALBUM` = the master title, or the release title when there is no master (the rule in discogs ADR 0002 §3). The lookup happens before any file is changed; if Discogs cannot be reached or the album has no Discogs ID, an artist/title override is not cleared and the error is shown. Clearing an override that is not set changes nothing, so saving the dialog never overwrites a hand-set `ALBUMARTIST`.

### Tracks tab
One row per file: disc, track, title, artist, disc subtitle, and a pen button that opens the lyrics editor ([0015](0015-track-playback-and-track-edit.md)). Only changed rows are sent. **`TITLE`, `DISCNUMBER` and `TRACKNUMBER` must not be empty**: the dialog and the server (400, checked before anything is written) refuse a row with an empty one. Writes `TITLE`, `DISCNUMBER`, `TRACKNUMBER`, `ARTIST`, `SET SUBTITLE` and `DISCSUBTITLE` (kept equal so it shows before the next fix). Files are renamed afterwards ([0010](0010-bliss-file-naming.md)).

### From Discogs tab: read-only
The tags `fixtags.py` writes from the release, shown as key and value and not editable: dates and years, `ALBUM`, `VERSION`, master/release titles and years, `ORIGINAL_TITLE`, `ALBUM_MAX_RESOLUTION`, country, labels, catalogue numbers, format, genres, styles, notes, series, data quality, `ALBUM_DR`, and the families `ALBUM_COMPANY_*`, `ALBUM_CREDIT_*`, `ALBUM_IDENT_*` and `DISCOGS_*` (written by the Discogs assignment, [0013](0013-discogs-track-assignment.md); `DISCOGS_RELEASE_ID` itself is shown on the Album tab). The player tags the assignment fills when empty (`GENRE`, `LABEL`, `COMPOSER`, ...) are ordinary tags and are not listed here. A note states that the overrides on the Album tab take precedence over `ALBUM` and `ALBUMARTIST`.

### Rules
- The editable list and the read-only list are constants in `app.py` (`ALBUM_FIELDS`, `DISCOGS_FIXED`, `DISCOGS_PREFIXES`) and mirror `fixtags.py` (the `DISCOGS_` prefix is Tagwright's own, from [0013](0013-discogs-track-assignment.md)). A change to `fixtags.py` that moves a tag between "user input" and "Discogs-derived" requires updating them and this ADR.
- A tag Discogs owns is never made editable here; to change it, change the release or add an override.
- Saves are refused while a job runs ([0008](0008-job-model.md)).

## Consequences

- No per-client setup. Free-form editing of arbitrary tags (composer, genre) is not offered because the pipeline neither writes nor needs them.
