# ADR 0098: Artwork per disc, and cover files rebuilt when library art changes

- **Status**: Accepted
- **Date**: 2026-11-22
- **Supersedes in part**: [0090](0090-artwork-types-and-cover-fields.md) ("writes are album-level") and [0091](0091-artwork-sidecars-on-move.md) (one set of cover files in the album folder; "nothing is ever overwritten"; "library sidecars are only created, never deleted")

## Context

Multi-disc releases often have different art per disc (a disc label, a booklet per disc). Since 0090 every artwork edit rewrote that picture type in every file, so a per-disc image could not be kept, and the cover files on disk (0091) were written only on a move and never refreshed. The owner asked to change images for one disc only, and for the cover files of a library album to be recreated when its art changes.

## Use cases (added to [0002](0002-purpose-scope-and-use-cases.md))

- **UC-21** Edit the embedded artwork of one disc of a multi-disc album without touching the other discs, and keep the album's cover files on disk in line with its embedded art.

## Decision

- **Disc of a file**: the leading number of its `DISCNUMBER` tag; no or an unreadable number is disc 1.
- **Disc switch**: when an album has files of more than one disc, a small pill above the four cover fields offers `All discs`, `Disc 1`, `Disc 2`, …. It starts at `All discs` for every album. `All discs` behaves as before: the fields show the distinct pictures of all files, and an edit writes that type to every file. `Disc N` shows only the pictures of that disc's files, and every edit (upload, drop, paste, delete, front cover included) writes only those files. The endpoints `GET /api/covers`, `GET/PUT/DELETE /api/cover` take an optional `disc`; `GET /api/covers` also returns `discs`, the disc numbers present. Deleting the front cover of one disc removes only that disc's front and untyped pictures; the staging folder images of [0024](0024-delete-cover-removes-folder-image.md) go only with an all-discs delete.
- **Cover files per folder** (replaces the single set of 0091): the audio files of the album folder are grouped by the folder they sit in. If they all sit in the album folder, it gets `folder.jpg` and `Artwork/` as in 0091. If they sit in disc folders (`Disc N`, `CD N`), every disc folder gets its own `folder.jpg` and `Artwork/` from its own files, and the album folder gets only `folder.jpg`, the front cover of the first disc folder. The naming inside each folder is that of 0091.
- **On a move** (Move to library, the watcher) cover files are still only created, never overwritten (0091), now per folder as above. The move preview lists them with their folder.
- **When art changes on a library album** (any artwork edit in the inspector on an album under the library folder), Tagwright rebuilds that album's cover files from the embedded art: `folder.jpg` and every `Artwork/` file are rewritten, `Artwork/` files and a `folder.jpg` that no embedded picture backs any more are deleted, an emptied `Artwork/` folder is removed, and in disc-folder albums an `Artwork/` folder left in the album folder is removed. The embedded art is the only source; files placed there by hand are replaced. Staging albums are not touched (their files are written on the move).

## Consequences

- A disc label or booklet can differ per disc and survives edits to other discs; an `All discs` edit makes that type the same on every disc again.
- A library album's cover files always match its embedded art after an edit in Tagwright; hand-made changes to those files are lost at the next edit.
- The inspector gains one control, shown only for multi-disc albums.
