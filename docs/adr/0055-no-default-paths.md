# ADR 0055: No default paths

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0045](0045-folders-from-the-environment-only.md) (the built-in defaults) and the mount and environment lines of [0003](0003-deployment-web-app-in-docker.md)

## Context

The built-in defaults for the two media folders were the owner's own layout. A fresh install that silently used them, or the repository's `./data`, would read and write folders nobody chose.

## Decision

- `STAGING_FOLDER`, `LIBRARY_FOLDER` and `DATA_DIR` have **no default**. Tagwright exits at start-up with "<name> is not set" when one is missing, and with "must be an absolute path" when one is relative. `PORT` keeps its default of 8080 (it is not a path).
- The image defines only `DATA_DIR=/data`, its own data mount point. `compose.yaml` sets `STAGING_FOLDER=/staging` and `LIBRARY_FOLDER=/library` and mounts the host paths `STAGING_HOST_PATH` and `LIBRARY_HOST_PATH` (from a `.env` file; compose refuses to start without them) there, and `./data` at `/data`.
- Running outside Docker means setting all three in the start command.

## Consequences

- A stack that relied on the old image defaults must set the two folder variables itself.
- Settings shows the host paths ([0045](0045-folders-from-the-environment-only.md)), so the container paths are not user-visible.
