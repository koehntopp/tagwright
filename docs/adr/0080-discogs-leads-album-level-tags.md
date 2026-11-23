# ADR 0080: Discogs leads the album-level tags; ARTIST goes with the title

- **Status**: Accepted; the format override is superseded by [0097](0097-album-format-is-a-plain-field.md); `ARTIST` as one joined value by [0100](0100-credits-one-value-per-name.md)
- **Date**: 2026-11-15
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) and [0013](0013-discogs-track-assignment.md) (the "filled only when the tag is empty" rule for `CATALOGNUMBER`, `ALBUM_FORMAT`, `ARTIST` and the credit tags), [0048](0048-reassignment-replaces-what-the-previous-release-filled.md) (for the keys below), [0014](0014-internal-tag-editor.md) (Album tab: Album Format and Catalog # become override fields)

## Context

Discogs is the leading system for album-level data ([0079](0079-discogs-assignment-sets-the-album-artist.md) did it for `ALBUMARTIST`). `CATALOGNUMBER`, `ALBUM_FORMAT` and the credit tags were only filled when empty, so a re-assignment or a corrected release left stale values, and `ARTIST` could stay at an old spelling while the title changed.

## Decision

A Discogs assignment (`POST /api/tracks/apply`) **writes from Discogs, whatever the files had**:

- `CATALOGNUMBER` (the other spellings are removed; Discogs' own `none` is written when the release has no number, [0047](0047-a-real-catalogue-number-replaces-none.md)) and `ALBUM_FORMAT`, each **unless its override tag is set**: `CATALOGNUMBER_OVERRIDE` and `ALBUM_FORMAT_OVERRIDE`, new, working like `ALBUM_ARTIST_OVERRIDE` ([0014](0014-internal-tag-editor.md)): the Tag Editor's Album tab fields "Album Format Override" and "Catalog # Override" write the override tag and the value itself to every file; saving them empty removes the override and restores the Discogs value (looked up like for the other overrides). The fields no longer need a value, because the Discogs value fills the tags.
- `COMPOSER`, `PRODUCER`, `ENGINEER` and the other player tags the assignment derives from the release's credits. When Discogs has no value for a tag, the file's value stays.
- `ARTIST` (the Discogs track artist, else the release artist) **whenever the title is written**, that is with "Import song titles" on ([0078](0078-musicbrainz-track-assignment-and-import-song-titles.md)); a re-assignment or a changed sequence therefore updates it. The MusicBrainz assignment does the same with the MusicBrainz track artist. With the box off `ARTIST` is only filled where a file has none.

Unchanged: a missing cover is embedded only where there is none; `ALBUM` and `ALBUMARTIST` keep their overrides; Run fixes does not write these tags (it keeps reading `ALBUM_FORMAT` and `CATALOGNUMBER` as input for the version string, which is why an override also writes them).

## Consequences

- Albums whose `ALBUM_FORMAT` or `CATALOGNUMBER` was set by hand before this ADR lose it at their next Discogs assignment, unless the owner first sets the override (the Tag Editor shows the current value under each field).
- The "previous release filled it" bookkeeping of 0048 only matters for `ARTIST` with the box off now.
- Tests: `tests/test_assign.py`, `tests/test_import_titles.py`.
