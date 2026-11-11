# ADR 0045: Staging and library folders come from the environment only

- **Status**: Accepted
- **Date**: 2026-11-11
- **Supersedes in part**: [0009](0009-settings-and-api-keys.md) (the two folders as settings, and their precedence over the environment)

## Context

In the Docker deployment ([0003](0003-deployment-web-app-in-docker.md)) the folders are fixed by the mounts (`/staging`, `/flac/ingest`). Editable fields in Settings could only break that, and a value saved in `settings.json` silently overrode `ROOT` and `INGEST_DIR`.

## Decision

- `ROOT` (staging) and `INGEST_DIR` (library) are read from the environment at start-up, with the defaults `/staging` and `/flac/ingest`. `settings.json` no longer holds them; `input` and `output` in it are ignored and dropped on the next save. `POST /api/settings` ignores `input` and `output` in the body.
- Settings shows both folders read-only. Under each it shows where the folder comes from on the host, read from `/proc/self/mountinfo`: the NFS export of the mount (`host:/export`) or the bind mount's host path. Where that is unknown (not Linux, or the folder is in the container's own layer) nothing is shown.

## Consequences

- Running outside Docker means setting `ROOT` and `INGEST_DIR` in the start command; moving to another folder needs a restart.
- The mount source is what the container sees; for a bind mount on a filesystem with subvolumes it can differ from the path on the host.
