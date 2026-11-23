# ADR 0104: Cover files for albums already in the library

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0091](0091-artwork-sidecars-on-move.md) (cover files are written only when tracks move into the library)

## Context

0091 writes `folder.jpg` and `Artwork/` when an album's tracks are placed in the library, by *Move to library* or by the watcher. Albums that were already in place when 0091 came (2026-11-21), and that have not moved since, never got them: 808 of the 819 library albums had no `folder.jpg`, although most embed a front cover and many a back cover, leaflet or media image (for example ELO, *Eldorado*, DCC Gold Disc).

## Decision

- On every **full pass** of the watcher (the first pass after a start, the daily sweep, *Re-analyze*), with *Apply* on, every library album that has a music folder (the album folder or a `Disc N` folder holding tracks) without `folder.jpg` gets its missing cover files written, exactly as 0091 and [0098](0098-artwork-per-disc.md) name them (`folder.jpg` per folder, `Artwork/NN type.jpg`, the box cover in the box folder).
- **Nothing is overwritten**, as in 0091: an album whose music folders all have a `folder.jpg` is not read at all, and inside an album that is, every existing file stays.
- One album at a time under the move lock, so *Move to library* waits at most for one album. The status line shows the album being written; the activity log says `wrote missing cover files for N album(s)`, and each album is logged.
- An album without any embedded picture gets nothing and is read again at the next full pass.

## Consequences

- The first full pass after this change reads the embedded pictures of most of the library once and writes their cover files.
- An album whose `folder.jpg` the owner deleted on purpose gets it back at the next full pass. Removing the embedded front cover is the way to have none.
- Albums that have a `folder.jpg` but miss `Artwork/` files (only possible from an earlier partial write) are not filled; an artwork edit in the inspector rebuilds them (0098).
