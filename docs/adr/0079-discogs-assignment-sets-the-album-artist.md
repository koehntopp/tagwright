# ADR 0079: ALBUMARTIST is a Discogs tag; the override is the exception

- **Status**: Accepted
- **Date**: 2026-11-15
- **Supersedes in part**: [0014](0014-internal-tag-editor.md) ("`fixtags.py` touches ALBUMARTIST only while the override is set"), [0053](0053-discogs-search-and-assignment-consolidated.md) and [0013](0013-discogs-track-assignment.md), the rule "filled only when empty" for `ALBUMARTIST`

## Context

The artist folder of the library comes from `ALBUMARTIST` ([0010](0010-bliss-file-naming.md), [0037](0037-library-watcher-and-layout.md)). A file that already carried a different spelling (`Simon and Garfunkel`, where Discogs says `Simon & Garfunkel`) kept it through an assignment, so the album landed in another artist folder than the same artist's other albums. The owner wants `ALBUMARTIST` to come from Discogs.

## Decision

`ALBUMARTIST` is **assigned from Discogs**, so that all albums are tagged consistently. The only way to another value is `ALBUM_ARTIST_OVERRIDE` ([0014](0014-internal-tag-editor.md)); `ALBUMARTIST` itself is not editable by hand.

- **Assignment** (`POST /api/tracks/apply`): replaces `ALBUMARTIST` on every assigned file with the release's artist names, whatever the file had, unless `ALBUM_ARTIST_OVERRIDE` is set.
- **Run fixes and the Discogs tags refresh** (`pipeline/fixtags.py`, `plan_tags`): write `ALBUMARTIST` on every file as `ALBUM_ARTIST_OVERRIDE` if set, else the release artists (`artist_names`: `(n)` suffixes dropped, join words kept). When Discogs names no artist the tag is left alone. Clearing an override restores the Discogs value as before.
- **Reorg and move** use no artist of their own: the library layout ([0037](0037-library-watcher-and-layout.md)) and the move target ([0011](0011-ingestion-move.md), `bliss_album`) read `ALBUMARTIST` from the files, which is the override or the Discogs artist, so they follow the tag as soon as an assignment or a run has written it. The watcher notices the changed files by their signature and re-plans; an album whose artist changed is placed in the new artist folder.

## Consequences

- Assigning a release or running the fixes can move an album into another artist folder of the library (the watcher places it by the new `ALBUMARTIST`); the artist spelling is now the Discogs one, which the owner prefers to a mix of spellings.
- An album that was fixed before this ADR keeps its old `ALBUMARTIST` until its next assignment or Run fixes: the status model ([0006](0006-status-model-and-pipeline-steps.md)) is not changed, so such an album still shows as fixed and can be moved with the old artist. Run fixes on the library album corrects it.
- An owner who wants another spelling sets Album Artist Override in the tag editor before or after the assignment.
- Tests: `tests/test_import_titles.py` (assignment), `tests/test_fixtags_pure.py` and `tests/test_fixtags_album.py` (Run fixes).
