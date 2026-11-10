# ADR 0023: MusicBrainz release search and tags

- **Status**: Accepted
- **Date**: 2026-11-09
- **Supersedes**: the out-of-scope bullet "MusicBrainz release search" of [0002](0002-purpose-scope-and-use-cases.md) (tracklist assignment stays out of scope)

## Context

UC-11. `MUSICBRAINZ_ALBUMID` anchors the language tags in `fixtags.py` ([0014](0014-internal-tag-editor.md)) and was a hand-typed tag. The owner asked for a MusicBrainz search that looks and works like the Discogs one ([0013](0013-discogs-track-assignment.md)), writing the release ID and the MusicBrainz links (release group = the "master", artist, album artist), and no track assignment. The library already carries tags written by the old tagger (Yate): `MUSICBRAINZ_RELEASE_GROUPID`, `MUSICBRAINZ_RELEASE_GROUP_URL`, `MUSICBRAINZ_ALBUM_URL`, `MUSICBRAINZ_LABEL_URL`, `MUSICBRAINZ_ALBUMSTATUS`, `MUSICBRAINZ_ALBUMTYPE`, ... The new tags use those names, so a file does not end up with two spellings.

## Decision

### Dialog (same shape as the Discogs dialog, [0017](0017-ui-layout-and-design-system.md))
- **Choose a MusicBrainz release**, 64 rem: a search field (artist and album, or a release ID) with **Search MusicBrainz**, a result table, **Cancel** and **Apply**. Opened by the pen next to the MusicBrainz ID badge in the inspector and by **Choose / Change release...** in the tag editor's Album tab (the button beside the Musicbrainz Release ID field, [0014](0014-internal-tag-editor.md)). With an existing `MUSICBRAINZ_ALBUMID` the dialog opens on that release.
- Result rows: cover thumbnail (Cover Art Archive `front-250`, loaded by the browser; a missing image is simply not shown), artist - title, country, format, label, barcode, **year in its own column**, **catalogue number in its own column** (monospace, also in the Discogs table), track count, **Select**. The **Year** and **Tracks** headers sort the list (same behaviour as the Discogs table, [0013](0013-discogs-track-assignment.md)). Selecting shows the release: the release ID, its release group (title, type, first release date) and the album artists as links, and the read-only tracklist (disc, track, title, artist, length). Nothing is assigned to files.

### Search (`GET /api/musicbrainz/search?q=&path=`, read-only)
- A release ID (UUID) loads that release. Otherwise every word of the query must match the release title or an artist (Lucene `(release:w OR artist:w) AND ...`, 20 results).
- **Discogs enhancement**: when the album has a `DISCOGS_RELEASE_ID`, the Discogs release is read (cached, [0013](0013-discogs-track-assignment.md)) and releases with the **same barcode** are searched first; only when that finds nothing, releases with the same **catalogue number** (up to two, `none` ignored). These come first in the list with a green "barcode match" / "catalog number match" badge. A missing Discogs key or a Discogs error is ignored and the plain search still runs.
- `GET /api/musicbrainz/release?id=&path=` returns the parsed release (cached for the life of the process) and the album's file count.

### Rate limit
MusicBrainz allows one request a second and wants a User-Agent naming the application (`Tagwright/0.2 (+https://github.com/koehntopp/tagwright)`, no contact data beyond the project URL). All calls go through one lock, at least 1.1 s apart; a 429 or 503 is retried three times after 5 s, then answered as 429; a 404 is 404, other errors 502. `urllib`, no new dependency ([0005](0005-technology-stack-and-conventions.md)). Searching with a Discogs enhancement takes a few seconds for that reason.

### Apply (`POST /api/musicbrainz/apply {path, id}`)
Refused (409) while a job runs ([0008](0008-job-model.md)). Written to **every file of the album**, replacing existing values (alternative spellings `MUSICBRAINZ ALBUM ID` and `MUSICBRAINZ_RELEASEGROUPID` are removed):

| Tag | Value |
|-----|-------|
| `MUSICBRAINZ_ALBUMID` | the release ID |
| `MUSICBRAINZ_ALBUM_URL` | `https://musicbrainz.org/release/<id>` |
| `MUSICBRAINZ_RELEASE_GROUPID` | the release group ID |
| `MUSICBRAINZ_RELEASE_GROUP_URL` | `https://musicbrainz.org/release-group/<id>` |
| `MUSICBRAINZ_ALBUMARTISTID` (multi) | the release's artist credit, artist IDs |
| `MUSICBRAINZ_ALBUMARTIST_URL` (multi) | `https://musicbrainz.org/artist/<id>` for each |

**Per file, only when its `TITLE` (normalised) equals exactly one release track**: `MUSICBRAINZ_ARTISTID` and `MUSICBRAINZ_ARTIST_URL` (multi) from that track's artist credit, replacing existing values. A file without such a match keeps whatever artist tags it has.

**Filled only where the tag is empty** (an existing value, from the Discogs assignment ([0013](0013-discogs-track-assignment.md)) or the owner, is never replaced): `BARCODE`, `ASIN`, `MUSICBRAINZ_ALBUM_RELEASECOUNTRY` (the MusicBrainz country code), `MUSICBRAINZ_ALBUMSTATUS` (Official, ...), `MUSICBRAINZ_ALBUMTYPE` (release group primary and secondary types, comma-joined, e.g. `Album,Compilation`) and `MUSICBRAINZ_ALBUM_DISAMBIGUATION`. Logged as `filled from MusicBrainz (only where empty): ...`. `COUNTRY` is not filled: Discogs writes a country name there and MusicBrainz a code. Titles, track and disc numbers and every other tag are not touched; no file is renamed. The log says how many files got artist links.

**Never written**: `MUSICBRAINZ_RELEASETRACKID` and `MUSICBRAINZ_TRACKID` (`fixtags.py` reads the release track ID to anchor languages per track, and Tagwright does no track assignment), and the tagger's other descriptive tags (`LABEL_URL`, `COVERART_URL`, `RELATIONSHIP_URL__DISCOGS`, ...); they stay as they are.

### Not changed
`fixtags.py` removes only the `ALBUM_COMPANY_`, `ALBUM_CREDIT_` and `ALBUM_IDENT_` families, so the new tags survive pipeline runs. Since 2026-11-10 the tag editor no longer has a text field for `MUSICBRAINZ_ALBUMID`: the ID is set through this dialog, which accepts a pasted ID ([0014](0014-internal-tag-editor.md)).

## Consequences

- No MusicBrainz tracklist assignment ([0002](0002-purpose-scope-and-use-cases.md) out of scope): picking a release never renumbers or retitles files.
- The thumbnails and the cover images come from coverartarchive.org straight to the browser; a release without art gives a 404 in the browser console that the app cannot avoid.
- Possible later additions, not built: original release date from the release group, label and catalogue number when empty, and the track IDs (needs a track assignment).
