# ADR 0105: The Artwork folder holds the front cover too; cover files follow every artwork change

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0091](0091-artwork-sidecars-on-move.md) (the names: `Artwork/` held only back, leaflet and media images) and [0098](0098-artwork-per-disc.md) (which artwork changes rebuild a library album's cover files)

## Context

The owner wants the `Artwork/` folder to be the complete set of an album's images, with a copy of `folder.jpg` in it, and wants the cover files to be written whenever files move or the artwork changes. Moves (0091) and the inspector's artwork edits (0098) did that; two other changes to the embedded art did not: the cover a Discogs assignment fetches for files without one, and the Tags & cover step scaling covers down to the maximum size.

## Decision

- Every folder that gets a `folder.jpg` also gets `Artwork/00 front.jpg` with the same image (the box folder of a box set too). Number `00` keeps the numbering of the other files (`01 back.jpg`, `02 booklet-01.jpg`, …) as it is, so existing files keep their names. The move preview lists it.
- A library album's cover files are rebuilt (0098: rewritten from the embedded art, stale ones removed) after every change Tagwright makes to its embedded art:
  - an upload, paste, replace or delete in the inspector (as before);
  - the cover a Discogs assignment embeds into files without one;
  - a Run fixes or a single step run on the album (the Tags & cover step may scale covers), and the Discogs tags refresh that a Tag Editor save or an assignment runs.
- Moves keep 0091's rule: the cover files are created, an existing one is never overwritten.
- The full-pass backfill of [0104](0104-cover-files-for-albums-already-in-the-library.md) also writes the missing `Artwork/00 front.jpg` of albums that already have `folder.jpg`; nothing is overwritten.

## Consequences

- After the next full pass every library album with an embedded front cover has `Artwork/00 front.jpg`.
- Staging albums get no cover files; they get them when they move to the library.
