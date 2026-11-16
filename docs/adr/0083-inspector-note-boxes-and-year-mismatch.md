# ADR 0083: One style for the inspector's note boxes; a year mismatch stops the move

- **Status**: Accepted
- **Date**: 2026-11-16
- **Supersedes in part**: [0023](0023-musicbrainz-release-search.md) (the year note never blocks a move: it is now a mismatch that does)

## Context

The inspector showed its notes in three looks (alert lines with rounded-lg corners, the Missing and Optional boxes, the folder lines), a year difference between Discogs and MusicBrainz had no type and was only a hint, red problems and blue hints carried the same triangle, and several boxes named a problem without a button to act on it.

## Decision

- **One box for every note**: the same corners and padding, the **type at the left** (uppercase, a column as wide as the longest label), the lines beside it, the **action button at the right**. Types and tones: **Problem** (red), **Mismatch** (red), **Missing** (red), **Warning** (amber), **Note** (blue) and **Optional** (blue). The folder box (light grey: **Current folder**, **New folder**, **In your library**, [0082](0082-in-your-library-box.md)) has the same shell and label column, without an icon or button.
- **Symbols**: a **stop symbol** (octagon with a cross) for the red types, a **warning sign** (triangle) for amber and blue ones.
- **Every box with something to do has a button**: the issue lines keep theirs (Search, Tag Editor, Upload); **Mismatch** and **Note** have **MusicBrainz** (opens the release dialog); **Missing** has **Run fixes** (disabled while a job runs or the album has no Discogs release ID, as the main button); when only Optional items exist, **Optional** carries the Run fixes button.
- **A year mismatch is red and stops the move.** When the album has both a Discogs release and a MusicBrainz release and their years differ, `GET /api/musicbrainz/check` returns it in `mismatches` (the other notes, the Discogs link and the track count, stay in `notes`, blue and non-consequential as in 0023). "Move to library" is disabled with the text as hover, and `move_plan()` (so the preview and `POST /api/move`) adds the problem "Year: Discogs A, MusicBrainz B. Fix the release before moving." The mismatch has **no override**: it is cleared by choosing the right MusicBrainz or Discogs release. It does not change the album's status or block Run fixes. When either service cannot be reached the move is not stopped (an unknown is not a mismatch).
- **New folder** has a second line under the path: the album title with its version string, formatted exactly like the lines of "In your library", so the two can be compared.

## Consequences

- An album whose Discogs and MusicBrainz releases legitimately differ in year (a reissue linked to the original's MusicBrainz release) cannot be moved until one of the two releases is changed. This was chosen over an "accept" button.
- The move preview calls MusicBrainz once for an album with both IDs (cached for the life of the process).
- Tests: `tests/test_mb_check.py` (year in `mismatches`, not in `notes`; the move plan refuses; an unreachable MusicBrainz does not).
