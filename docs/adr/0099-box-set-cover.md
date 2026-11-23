# ADR 0099: A box-set cover beside the disc covers

- **Status**: Accepted (a shared front instead of an empty Box Cover: [0107](0107-all-discs-shows-a-shared-front-instead-of-an-empty-box-cover.md))
- **Date**: 2026-11-22
- **Supersedes in part**: [0098](0098-artwork-per-disc.md) (the album folder's `folder.jpg` is the first disc's front cover; `All discs` edits the front cover of every file)

## Context

Box sets have a cover of their own, and disc 1 often has a different one. Roon reads an image in the box's top folder as the box cover and an image in each disc folder as that disc's cover ([Roon: Disc Titles, Covers, and Years in Multi-Disc Box Sets](https://help.roonlabs.com/portal/en/kb/articles/box-sets-how-to-check-your-files)). Roon has no tag for a box cover, and FLAC and ID3 have no picture type for one. Since 0098 the album folder took disc 1's front, so a new disc 1 cover replaced what Roon showed for the whole box.

## Decision

- **Storage**: the box cover is a front-cover picture (type 3) whose description is `Box set`, embedded in every file of the album. A disc's own cover is a front-cover picture with any other description, only in that disc's files. Both may sit in one file (FLAC allows several pictures of a type; ID3 allows several `APIC` frames with different descriptions). **The disc cover comes first** in each file, the box cover after it, so players that show the first embedded front show the disc's cover.
- **Inspector**: on an album with more than one disc, the first field under `All discs` is **Box Cover** and edits only the box picture of every file; under `Disc N` the **Front Cover** field edits only that disc's cover and leaves the box picture alone. Single-disc albums keep one Front Cover as before. The API treats the box as pseudo-type `100` (`type=100` on `/api/cover`; `/api/covers` returns it as `box`); it is never written as a picture type.
- **Cover files** (0098's layout): the album folder's `folder.jpg` is the box cover; without one, the first disc's front as before. A disc folder's `folder.jpg` is that disc's front; without one, the box cover. A single-folder album uses the box cover when it has one, else its front.
- **Album card / thumbnail**: the box cover when there is one, else the first front as before.
- Removing the front cover of all discs (single-disc albums, [0024](0024-delete-cover-removes-folder-image.md)) still removes every front picture, the box picture included.

## Consequences

- Roon shows the box cover for the box and each disc's own cover for the discs, from files Tagwright writes.
- A multi-disc album that is not a box can use Box Cover as its common cover; the description says `Box set` there too.
- Albums that already have one front in every file show no Box Cover until one is set; their folder image still comes from disc 1.
