# ADR 0097: Album Format is a plain field, without an override tag

- **Status**: Accepted
- **Date**: 2026-11-22
- **Supersedes in part**: [0080](0080-discogs-leads-album-level-tags.md) (`ALBUM_FORMAT_OVERRIDE` and the "Album Format Override" field) and [0014](0014-internal-tag-editor.md) (the Album tab's format field)

## Context

The owner reported that the Tag Editor does not show the album's existing format. Since 0080 the Album tab had an "Album Format Override" field that stayed empty unless `ALBUM_FORMAT_OVERRIDE` was set; the current value appeared only in small print under it. The owner's rule: an album without a format of its own is `CD`; a Discogs assignment fills the format from the release; the user may type over it like any other field, with no override tag.

## Decision

- The Album tab's field is **Album Format**. It shows and writes `ALBUM_FORMAT` itself. Saving a value writes it to every file and removes a legacy `ALBUM_FORMAT_OVERRIDE`; saving it empty removes `ALBUM_FORMAT`, and the Discogs tags step writes `CD` (or `SUBTITLE`) as before. Editing it rewrites `VERSION` at once, as for the edition and catalogue number ([0049](0049-tag-edits-refresh-the-version-at-once.md)).
- A Discogs assignment still writes `ALBUM_FORMAT` from the release ([0080](0080-discogs-leads-album-level-tags.md)); assigning a release is the explicit act that replaces a typed format. An album that still carries a legacy `ALBUM_FORMAT_OVERRIDE` keeps its value on assignment until the field is saved.
- `CATALOGNUMBER_OVERRIDE` and the other overrides are unchanged.

## Consequences

- The field always shows what the files say, and `ALBUM_FORMAT` stays a user-owned tag the Discogs tags step only reads.
- Typing a format and later assigning a release replaces it with the release's format.
