# ADR 0100: Artists and credits one value per name; legacy tags removed; required tags never lost

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) (the `ARTIST`, `COMPOSER`, `PRODUCER`, `ENGINEER` and `PERSONNEL` rows of the filled-tags table), [0080](0080-discogs-leads-album-level-tags.md) (`ARTIST` as one joined value)

## Context

Deep Roon reported messy credits on a library album (Adele, *25*). The files held one `COMPOSER` value per track with the names joined by commas (`Adele Adkins,Greg Kurstin`), written by the tagger used before Tagwright. Roon reads a joined value as one name. A library survey (first file of each of 965 albums) found joined values in `COMPOSER` (196 albums), `ARTIST` (16), `LYRICIST` (12), `REMIXER` (9) and `CONDUCTOR` (2). It also found credit lists in formats Roon does not read (`PERFORMERYR`, `INVOLVEDPEOPLEYR`, `INVOLVEDPEOPLE`, `PERFORMER` as `Name (Role)`), and ripper or tagger leftovers that nothing reads.

The assignment wrote `COMPOSER`, `PRODUCER` and `ENGINEER` as separate values since 0080, but had several gaps:

- It wrote no `MIXER`, `LYRICIST`, `ARRANGER`, `CONDUCTOR` or `REMIXER`.
- It put lyricists into `COMPOSER`.
- It ignored the track range of release credits ("tracks 1 to 3"), so those credits landed on every track.
- It wrote `PERSONNEL` with Discogs role text Roon may not recognise.
- It wrote `ARTIST` as one joined string.

Roon reads `COMPOSER`, `LYRICIST`, `ARRANGER`, `CONDUCTOR`, `REMIXER`, `MIXER`, `PRODUCER`, `ENGINEER` and `ENSEMBLE`. It also reads `PERSONNEL` as `Name - Role`, one value per credit, for every other role ([Roon: File Tag Best Practice](https://help.roonlabs.com/portal/en/kb/articles/file-tag-best-practice)). Roon has no dedicated mastering tag.

## Decision

The rules live in `pipeline/credits.py`. The Discogs assignment (UC-6) and the one-off script `scripts/fix-credits.py` both use them.

- **One value per name** for `ARTIST` and every credit tag.
- **Where a track's credits come from**:
  - Its own Discogs credits; a part of a medley also takes its entry's.
  - Release credits whose `tracks` range covers it (`1 to 3, 5`, `A2 to B1`).
  - A dedicated tag that gets nothing from those falls back to the release-wide credits (no range).
  - `PERSONNEL` always includes the release-wide credits.
- **ARTIST**: the track's artists, else the release artists. The `(n)` suffix is dropped and the join words go.
- **Discogs role to tag** (role compared without its `[qualifier]`):

  | Tag | Discogs roles |
  |-----|---------------|
  | `COMPOSER` | Written-By, Composed By, Music By, Songwriter |
  | `LYRICIST` | Lyrics By, Words By |
  | `ARRANGER` | roles containing "Arranged By" |
  | `CONDUCTOR` | Conductor |
  | `REMIXER` | roles containing "Remix" |
  | `MIXER` | Mixed By |
  | `PRODUCER` | roles containing "Producer" |
  | `ENGINEER` | Recorded By, roles containing "Engineer" |
  | `PERSONNEL` | every other role, as `Name - Role` |

  In `PERSONNEL`, "Mastered By" is written as Mastering Engineer, "Programmed By" as Programming, and any other "X By" as X.
- **Assignment**: every one of these tags is led by Discogs ([0080](0080-discogs-leads-album-level-tags.md)): replaced when Discogs has a value, kept when it has none. `ARTIST` still goes with the title (Import song titles on; otherwise it is filled only when empty).
- **Legacy tags are removed** on assignment and by the script:
  - Credit lists: `PERFORMER`, `PERFORMERYR`, `INVOLVEDPEOPLE`, `INVOLVEDPEOPLEYR`.
  - The old tagger's `DISCOGS …` keys with a space.
  - `RETAIL DATE`, `RIP DATE`, `RELEASE TYPE`, `ORGANIZATION`.
  - The four `(ALBUM) DYNAMIC RANGE (DR/R128)` keys.
  - `ORIGINALYEAR`, `TRACKNUM`, `DISC`, `TRACK`, `ALBUMARTIST2`, `ARTISTS`.
  - ffmpeg's `_STATISTICS_*`, `NUMBER_OF_FRAMES`, `NUMBER_OF_BYTES`, `BPS`, `DURATION`, `LENGTH`.
  - `APISEEDS_STATUS`, `GET_LYRICS_STATUS`.

  The list is `credits.LEGACY_TAGS` and `LEGACY_PREFIXES`.
- **Required tags are never lost**: an update that would leave `TITLE`, `ARTIST`, `ALBUM`, `ALBUMARTIST`, `TRACKNUMBER` or `DISCNUMBER` empty when it had a value is not saved, so a broken Discogs answer cannot strip a file. The assignment logs `<file>: not saved, it would lose …`; the script reports and skips the file.
- **Tag Editor, Tracks tab**: a multi-value `ARTIST` is shown as `A; B` and saved split at `;`.
- **`scripts/fix-credits.py`** (run from the Mac against the mounted library, not in the container):
  - Looks each album's release up again and applies the rules above, without touching titles or numbers.
  - Matches a file to its track by `TRACK_NUMBER_TEXT`, else by `DISCOGS_RELEASE_ORDINAL_POSITION` checked against the position. Older writers counted headings in the ordinal.
  - Splits a joined credit at commas and semicolons when Discogs has nothing for that tag.
  - Replaces `ARTIST` only when the file names the same artists joined into one value, and reports any other difference.
  - Runs as a dry run with a diff by default; `--write` saves.

## Consequences

- Roon sees each composer, writer, mixer and engineer as a person, and mastering, photography and the like through `PERSONNEL`.
- Release credits limited to some tracks no longer appear on every track.
- Albums assigned before this ADR are fixed by running the script once; later assignments write the same.
- Splitting a joined value without Discogs data can split a name that contains a comma; the dry run shows it first.
- `ENGINEER` includes assistant engineers (qualifiers are not kept in dedicated tags).
