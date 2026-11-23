# ADR 0091: Artwork sidecars when an album enters the library

- **Status**: Accepted (one set per album and never-overwrite in the library superseded in part by [0098](0098-artwork-per-disc.md); albums already in the library get theirs from [0104](0104-cover-files-for-albums-already-in-the-library.md); `Artwork/00 front.jpg`: [0105](0105-artwork-folder-holds-the-front-cover-too.md))
- **Date**: 2026-11-21
- **Supersedes in part**: [0011](0011-ingestion-move.md) ("covers, logs and other files stay behind") and [0037](0037-library-watcher-and-layout.md) ("only the FLACs move") for artwork sidecars; the rest of both ADRs stands

## Context

The embedded artwork is the source of truth ([0090](0090-artwork-types-and-cover-fields.md)). A music server that does not read embedded art needs images on disk next to the tracks. Today a Move to library carries only audio files, so the library has no cover files; and the watcher moves files inside the library with the same executor.

## Use cases (added to [0002](0002-purpose-scope-and-use-cases.md))

- **UC-20** Recreate an album's cover files on disk from its embedded artwork whenever the tracks move into the library.

## Decision

- When an album's audio files are placed in the library — by **Move to library** or by the **library watcher** — Tagwright writes artwork files beside them, using the album folder the layout chose:
  - the **front cover** (type 3) becomes `folder.jpg` in the album folder;
  - the other images go into an `Artwork/` subfolder, numbered across types in type order (back, leaflet, media): `01 back.jpg`, `02 booklet-01.jpg`, `03 booklet-02.jpg`, `04 disc.jpg`. A second back image is `back-02.jpg`; further media images are `disc-02.jpg` and so on.
- Pictures with identical bytes are written once. The order follows the files in disc/track order and the order of pictures inside each file. Non-JPEG pictures are written as JPEG; an image that cannot be decoded is written unchanged with its original bytes.
- **Nothing is ever overwritten or merged**: a sidecar that already exists is left as it is, so a second pass cannot clobber art put there by the owner. The move itself still refuses when an audio target exists ([0011](0011-ingestion-move.md), [0037](0037-library-watcher-and-layout.md)).
- The preview (`GET /api/move/preview`) lists the artwork files that will be created, so the move dialog shows the whole result before it happens.
- The embedded pictures are not changed by the export. Deleting the embedded front cover still removes the *staging* folder images of [0024](0024-delete-cover-removes-folder-image.md); library sidecars are only created, never deleted here.
- Extraction is a helper of `pipeline/` (artwork read/write already lives there), called by both `app.py` and `library/executor.py`. No new dependency: Pillow is already used.

## Consequences

- A move to the library always leaves a complete set of cover files, and the watcher can recreate them later if the embedded art changes and the files are moved again.
- An existing `folder.jpg` or `Artwork/` file wins over the embedded version; replace it by hand if the embedded art is meant to take over.
- Albums without embedded art get no sidecars and keep the minimum-cover-size warning of [0016](0016-cover-art.md).
