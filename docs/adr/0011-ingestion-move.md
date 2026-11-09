# ADR 0011: Moving fixed albums to the ingest folder

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

UC-5: once an album is fully fixed it should leave the input folder for the folder the music server ingests.

## Decision

- "Move to ingest" is enabled only for albums with status `fixed` ([0006](0006-status-model-and-pipeline-steps.md)); the server re-checks and answers 409 otherwise.
- The album folder is moved with `shutil.move` to `INGEST/<folder name>`. If that path exists the move is refused (409); nothing is overwritten or merged.
- Partial steps (yellow) count as done, so an album with plain-text lyrics can be moved; the decision to ingest it is the user's. A cover below the minimum size is different: it is an `ingest`-level issue: the album can still be fixed (status unchanged) but cannot be moved until the cover is replaced or the minimum is lowered ([0016](0016-cover-art.md)).
- The move is refused while a job runs ([0008](0008-job-model.md)). After a move the album disappears from the input list.
- The ingest folder is created if missing.

## Consequences

- A move is not undone by Tagwright. Moving across volumes copies first, so it can be slow on network shares.
