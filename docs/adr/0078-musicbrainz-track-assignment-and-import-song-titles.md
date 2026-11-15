# ADR 0078: MusicBrainz track assignment, and "Import song titles" in both dialogs

- **Status**: Accepted
- **Date**: 2026-11-15
- **Supersedes in part**: [0023](0023-musicbrainz-release-search.md) (Apply writes no titles, track numbers or renames) and the out-of-scope bullet "MusicBrainz tracklist assignment" of [0002](0002-purpose-scope-and-use-cases.md); extends [0013](0013-discogs-track-assignment.md) and [0053](0053-discogs-search-and-assignment-consolidated.md)

## Context

Japanese releases often carry kanji in the titles Discogs gives; MusicBrainz usually has the title the owner wants in the file name. Until now only Discogs assigned tracks and wrote `TITLE`; the MusicBrainz dialog wrote IDs and links only, so there was no way to let MusicBrainz overwrite titles. The owner asked that both dialogs look and work the same, with a checkbox that decides whether titles are imported.

## Decision

1. **The MusicBrainz dialog assigns tracks like the Discogs one.** After a release is picked, the dialog shows the same file -> release track table (proposal, manual choice, disc and track overrides, Skip, match / check badges). `POST /api/tracks/propose` takes `source` (`discogs`, the default, or `musicbrainz`; the `release_id` is then the MusicBrainz release ID) and scores exactly as in 0013, with MusicBrainz tracks carrying `disc`, `track` (position on the medium), `position` and no medley parts. The release block above the table (release, release group, album artist) stays.
2. **Apply** (`POST /api/musicbrainz/apply {path, id, assignments, import_titles}`, 409 while a job runs). The release ID, release group and album artist tags and the filled-only-where-empty tags are written exactly as in 0023. With `assignments`, each assigned file also gets its `MUSICBRAINZ_ARTISTID` and `MUSICBRAINZ_ARTIST_URL` from the assigned track (not from a title match), and, only when **"Import song titles"** is on, `TITLE`, `TRACKNUMBER`, `DISCNUMBER`, `TRACKTOTAL`/`TOTALTRACKS` and `DISCTOTAL`/`TOTALDISCS` (same numbering rule as 0013: 1..n per disc in release order, the dialog may override). Files set to Skip keep everything but the album-level tags. Then the files are renamed ([0010](0010-bliss-file-naming.md)). Without `assignments` the endpoint behaves as in 0023 (artist links by exact title match, nothing renumbered).
3. **"Import song titles" checkbox in both dialogs**, under the assignment table. Off: only the album data is imported (release IDs and links, catalogue number, year, country and the other album tags); the files keep their `TITLE`, track and disc numbers, totals and disc subtitles, and the dialog greys out the disc and track fields. On: the title, track number and disc number (with the totals) and the disc subtitle are written too. The disc subtitle is written as `SET SUBTITLE` and `DISCSUBTITLE` (the pair the tag editor writes) on every assigned file of that disc, only where the release has one. On Discogs it is the heading right before a disc's first track, without a leading `CD n` / `Disc n` label (a heading that is only that label gives none; later headings inside a disc are ignored); on MusicBrainz it is the medium's title. The release answers carry them as `discs: [{disc, title}]` and the dialog lists them under the checkbox. The server keeps one saved value per source in the settings file: `import_titles_discogs` (default **on**) and `import_titles_musicbrainz` (default **off**). The value sent with an apply is saved; the next dialog starts with it (`import_titles` in the propose and release answers). Without the field in a request the saved value is used, so older clients keep working.
4. **Not touched**: the Discogs-owned per-track tags (`DISCOGS_RELEASE_ORDINAL_POSITION`, `TRACK_NUMBER_TEXT`) are not rewritten by a MusicBrainz assignment; they describe the Discogs release and the next Discogs assignment replaces them. A MusicBrainz apply does not run the Discogs tags step.
5. Use case UC-11 of 0002 now includes assigning the album's files to the release's tracks.

## Both dialogs look and work the same

The Discogs and the MusicBrainz dialog **must stay consistent**: they use one shared table component and one checkbox component (`AssignTable`, `TitlesBox` in `ui/components/releases.tsx`), and a change to how assignment, titles, numbers or the checkbox look or behave is made once for both. Specifically:

- With "Import song titles" **on**, each assigned file shows an **editable title field** under its release track choice, filled with the release's title, so a title can be corrected during the import. Under it, in small light grey text, `Was: <the file's current title>` with a copy button. The typed title is sent as `title` in the assignment and written instead of the release's title (a blank field means the release's title).
- Whatever the apply will **not change** is shown light grey: with the box off the disc and track fields (and the disc subtitles line) are grey and disabled, and the title fields are not shown.
- Hints under the table name tags in capitals.

## Consequences

- With "Import song titles" on, a MusicBrainz apply can replace Discogs titles and, through the rename, file names; renumbering and renaming follow the chosen release's track order.
- A Discogs assignment with the box off keeps the titles and numbers the files have, including ones Discogs would have replaced; fixing them stays a manual edit in the tag editor.
- The MusicBrainz dialog no longer lists the track artists and lengths in a table of its own; the track choices in the assignment table show title, length and channels.
