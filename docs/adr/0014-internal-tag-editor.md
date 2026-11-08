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
| `ALBUM_ARTIST_OVERRIDE` | also written to `ALBUMARTIST` immediately |
| `ALBUM_TITLE_OVERRIDE` | also written to `ALBUM` immediately |
| `ALBUM_FORMAT` | for example CD, SACD (empty: CD) |
| `ALBUM_EDITION` | part of the version string |
| `SUBTITLE` | format fallback |
| `CATALOGNUMBER` | part of the version string; alternative spellings are removed on clear |
| `MUSICBRAINZ_ALBUMID` | anchors language tags |

Also shown: the Discogs release ID as a link, with "Change release…" ([0013](0013-discogs-track-assignment.md)). The ID itself is changed only through that dialog.

The pencils next to the album artist and the album title in the inspector header open a small dialog for the two override fields; both write the same tags through the same code.

### Tracks tab
One row per file: disc, track, title, artist, disc subtitle, and a pen button that opens the lyrics editor ([0015](0015-track-playback-and-track-edit.md)). Only changed rows are sent. Writes `TITLE` (required), `ARTIST`, `DISCNUMBER`, `TRACKNUMBER`, `SET SUBTITLE` and `DISCSUBTITLE` (kept equal so it shows before the next fix). Files are renamed afterwards ([0010](0010-bliss-file-naming.md)).

### From Discogs tab: read-only
The tags `fixtags.py` writes from the release, shown as key and value and not editable: dates and years, `ALBUM`, `VERSION`, master/release titles and years, `ORIGINAL_TITLE`, `ALBUM_MAX_RESOLUTION`, country, labels, catalogue numbers, format, genres, styles, notes, series, data quality, `ALBUM_DR`, and the families `ALBUM_COMPANY_*`, `ALBUM_CREDIT_*`, `ALBUM_IDENT_*`. A note states that the overrides on the Album tab take precedence over `ALBUM` and `ALBUMARTIST`.

### Rules
- The editable list and the read-only list are constants in `app.py` (`ALBUM_FIELDS`, `DISCOGS_FIXED`, `DISCOGS_PREFIXES`) and mirror `fixtags.py`. A change to `fixtags.py` that moves a tag between "user input" and "Discogs-derived" requires updating them and this ADR.
- A tag Discogs owns is never made editable here; to change it, change the release or add an override.
- Saves are refused while a job runs ([0008](0008-job-model.md)).

## Consequences

- No per-client setup. Free-form editing of arbitrary tags (composer, genre) is not offered because the pipeline neither writes nor needs them.
