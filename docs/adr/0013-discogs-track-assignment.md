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

### Tracklist
Entries of type `track` only (headings and index entries are skipped). Position `D-T` or `CDD-T` gives disc and track; any other position (vinyl `A1`, plain numbers, empty) is numbered sequentially on disc 1. Track artists come from the release's per-track artists, else the release artists; the Discogs `(n)` disambiguation suffix is removed.

### Proposed assignment
`POST /api/tracks/propose` scores every file against every release track: title similarity x 0.6, duration closeness (within 8 s, x 0.25, only if Discogs has a duration), same disc and track number x 0.15. Pairs are taken greedily from the highest score; scores below 0.35 stay unassigned. Titles dominate because Discogs durations are often several seconds off.

### Adjusting and applying
- The dialog lists each file with a dropdown of release tracks (or "Skip") and a match/check/skip badge; release tracks not used are listed as "Not in this album". One release track cannot be given to two files (Apply is disabled).
- Disc and track numbers are editable per file. Default: tracks are renumbered `1..n` per disc in release order over the **selected** files, discs renumbered from 1, so a subset has no gaps.
- `POST /api/tracks/apply` writes per assigned file: `DISCOGS_RELEASE_ID`, `TITLE`, `TRACKNUMBER`, `DISCNUMBER`, `TRACKTOTAL` and `TOTALTRACKS` (files on that disc), `DISCTOTAL` and `TOTALDISCS` (distinct discs). Files set to Skip are untouched. Then files are renamed ([0010](0010-bliss-file-naming.md)).
- **Track `ARTIST` is never written.** It is a tagger tag and can carry rip-specific billing (for example "Roy Orbison With Guests") that the library folder name and the lyrics lookup depend on (discogs ADR 0002 §1 and §6). The Discogs track artists are parsed and returned by the API but never applied.
- Discogs release positions are not stored in a tag, because `fixtags` removes tag families it manages.

### Entry points
"Change release…" / "Choose release…" in the tag editor ([0014](0014-internal-tag-editor.md)) and the Search button on albums that need IDs.

## Consequences

- MusicBrainz tracklists are not supported.
- Requires a Discogs key ([0009](0009-settings-and-api-keys.md)).
