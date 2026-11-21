# ADR 0090: Artwork types and four cover fields

- **Status**: Accepted (the field controls are superseded by [0092](0092-cover-controls-and-full-size-view.md))
- **Date**: 2026-11-21
- **Supersedes in part**: [0056](0056-cover-controls-in-one-menu.md) (the cover menu under the action row), and the one-image cover model of [0016](0016-cover-art.md) and [0042](0042-covers-are-scaled-on-upload.md)

## Context

Covers are embedded pictures in the audio files (types 3 front, 4 back, 5 leaflet, 6 media). The inspector shows only the front cover, in one 144 px box beside the metadata, with its controls in a menu under the action row. A release can also carry back art, booklet pages and a disc image; the owner wants those editable in the same place, and wants the metadata to use the full inspector width.

## Use cases (added to [0002](0002-purpose-scope-and-use-cases.md))

- **UC-19** See and edit the embedded artwork of an album by type in the inspector: one front cover and any number of back, leaflet and media images.

## Decision

- Embedded pictures are grouped by their standard picture type: **3 Front Cover**, **4 Back Cover**, **5 Leaflet page**, **6 Media**. Pictures of other types are left untouched.
- **Front cover holds at most one image**; Back Cover, Leaflet and Media can hold several. Images repeated with the same bytes in several files of an album are one image, in first-seen order.
- The inspector's top line is the album metadata (artist, title, version/year, Discogs and MusicBrainz badges and DR) across the full inspector width. Directly below it is a four-column grid of equally wide cover fields: **Front Cover**, **Back Cover**, **Leaflet**, **Media** in that order.
  - An empty field is a dashed drop target with a small upload hint. Dropping or uploading an image adds it; clicking the target opens a file picker.
  - The front field shows one image, with **Replace**, **Remove** and a small menu holding **Paste image** and the two cover search links of [0056](0056-cover-controls-in-one-menu.md). A front cover below the minimum size gets the same amber warning outline as before ([0016](0016-cover-art.md)); no other field is coloured by size.
  - The other three fields show the selected image, a `‹ n / total ›` pair of buttons to cycle, and **Replace**, **Delete** and **Add** actions. Deleting removes only the selected image; Add appends one.
  - All uploads are verified images and scaled to `cover_max_size` at once, as in [0042](0042-covers-are-scaled-on-upload.md). An image within the limit is stored unchanged.
- Writes are **album-level**: changing a type rewrites that type's pictures in every audio file of the album and leaves every other picture type alone ([0004](0004-pipeline-engine-reuses-discogs-scripts.md): automation never overwrites art it does not own). The front edit keeps the existing behaviour of replacing type 0 and 3 pictures ([0024](0024-delete-cover-removes-folder-image.md)); a type-specific delete removes only that type.
- **API**: `GET /api/covers?path=` lists the images by type with their size and a URL; `GET /api/cover?path=&type=&index=` serves one picture (without `type` it still serves the old front/first/folder image, so cards are unchanged). `PUT /api/cover` and `DELETE /api/cover` take optional `type` and `index` query parameters, defaulting to the front cover as today. All writes are refused with 409 while a job runs ([0008](0008-job-model.md)) and use `safe()` ([0007](0007-trust-boundary-and-secrets.md)).
- The folder images of [0024](0024-delete-cover-removes-folder-image.md) are still removed by a front-cover delete; generated library sidecars are governed by [0091](0091-artwork-sidecars-on-move.md).

## Consequences

- A release's back cover, booklet and disc art can be curated once and stays embedded in every file.
- The inspector's metadata gets the full width; the cover fields are compact and equal, which keeps the four types comparable.
- The old cover-menu location is gone; its Paste and search actions live in the front field's menu.
- Only the front cover affects the minimum-size gate and the card thumbnail; other artwork is optional.
