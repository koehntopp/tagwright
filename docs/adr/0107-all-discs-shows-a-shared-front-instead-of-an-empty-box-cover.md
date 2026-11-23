# ADR 0107: All discs shows a shared front cover instead of an empty Box Cover

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0099](0099-box-set-cover.md) ("on an album with more than one disc, the first field under `All discs` is **Box Cover**")

## Context

On a two-disc album whose discs carry the same front cover (The Alan Parsons Project, *Tales Of Mystery And Imagination*, Blu-ray: both discs embed the same 443 KB image) the `All discs` view showed an empty **Box Cover** field. The files were right: the top folder's `folder.jpg` falls back to the first disc's front (0099). The owner asked whether the box cover should be pulled up from the discs. Writing a copy of the disc front as a "Box set" picture into every file adds data and no information, and when the discs' fronts differ Tagwright cannot tell which one stands for the box. The empty field was the problem, not the files.

## Decision

- Under `All discs` on a multi-disc album, the first field is:
  - **Front Cover** when there is no box cover and every disc has the same front cover (one distinct front picture, or none). It shows that front; an upload, paste, replace or delete writes the front of every file, as on a single-disc album.
  - **Box Cover** (as in 0099) when a box cover exists or the discs' front covers differ. While it is empty it shows the first disc's front, greyed, with the note "No box cover; folder.jpg uses Disc 1's cover"; it offers Upload (no Delete), and nothing is written until a box cover is set.
- Nothing is written automatically; the embedded pictures and the cover files stay as 0099 and [0098](0098-artwork-per-disc.md) make them.
- The macOS port follows.

## Consequences

- A multi-disc album that is really one album with one cover looks like one; a real box set keeps its own field.
- Setting a front cover under `All discs` on a shared-front album replaces every disc's front; a disc that should differ is set under its own disc.
