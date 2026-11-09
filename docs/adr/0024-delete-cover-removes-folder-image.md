# ADR 0024: Delete cover also removes the folder image

- **Status**: Accepted
- **Date**: 2026-11-09
- **Supersedes**: the **Delete** bullet of [0016](0016-cover-art.md) (the rest of 0016 stands)

## Context

The cover box shows the embedded front cover, else a folder image (`cover.jpg`, `folder.jpg`, `cover.png`, `folder.png`). After Delete removed the embedded pictures the red x disappeared but the folder image was still shown, so the cover looked undeleted. The owner chose to remove the folder image too.

## Decision

- The red circle-x is shown whenever the album has a cover, embedded or a folder image.
- `DELETE /api/cover?path=` removes the front and untyped (type 0 and 3) pictures from every FLAC, keeping other picture types, and deletes the folder image files named above from the album folder. Other files in the folder are not touched. Refused (409) while a job runs.
- The in-app confirmation names what goes: the embedded cover and any folder image.
- The album then has no cover, so the minimum-size rule applies ([0006](0006-status-model-and-pipeline-steps.md)).

## Consequences

- Deleting a folder image cannot be undone by Tagwright.
