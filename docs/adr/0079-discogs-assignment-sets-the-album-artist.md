# ADR 0079: The Discogs assignment sets ALBUMARTIST

- **Status**: Accepted
- **Date**: 2026-11-15
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) and [0013](0013-discogs-track-assignment.md), the rule "filled only when empty" for `ALBUMARTIST`

## Context

The artist folder of the library comes from `ALBUMARTIST` ([0010](0010-bliss-file-naming.md), [0037](0037-library-watcher-and-layout.md)). A file that already carried a different spelling (`Simon and Garfunkel`, where Discogs says `Simon & Garfunkel`) kept it through an assignment, so the album landed in another artist folder than the same artist's other albums. The owner wants `ALBUMARTIST` to come from Discogs.

## Decision

A Discogs assignment **replaces** `ALBUMARTIST` on every assigned file with the release's artist names, whatever the file had. The one exception stays: while `ALBUM_ARTIST_OVERRIDE` is set the tag is not touched ([0014](0014-internal-tag-editor.md): the override is how the owner keeps a different value). An empty Discogs artist writes nothing. The log counts it under `filled from Discogs: ALBUMARTIST xN`. Every other tag in the "filled only when empty" table of 0053 keeps its rule.

## Consequences

- Assigning a release can move an album into another artist folder of the library (the watcher places it by the new `ALBUMARTIST`); the artist spelling is now the Discogs one, which the owner prefers to a mix of spellings.
- An owner who wants another spelling sets Album Artist Override in the tag editor before or after the assignment.
- Tests: `tests/test_import_titles.py` (a different album artist is replaced, an override is not).
