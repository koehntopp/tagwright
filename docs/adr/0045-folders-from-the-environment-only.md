# ADR 0045: Staging and library folders come from the environment only

- **Status**: Accepted (the defaults are gone: [0055](0055-no-default-paths.md))
- **Date**: 2026-11-11
- **Supersedes in part**: [0009](0009-settings-and-api-keys.md) (the two folders as settings, and their precedence over the environment)

## Context

In the Docker deployment ([0003](0003-deployment-web-app-in-docker.md)) the folders are fixed by the mounts (the container paths). Editable fields in Settings could only break that, and a value saved in `settings.json` silently overrode the environment.

## Decision

- `STAGING_FOLDER` and `LIBRARY_FOLDER` are read from the environment at start-up, with no default ([0055](0055-no-default-paths.md)). `settings.json` no longer holds them; `input` and `output` in it are ignored and dropped on the next save. `POST /api/settings` ignores `input` and `output` in the body.
- Settings shows both folders read-only, as host paths, not as the container's mount points: the NFS export of the mount (`host:/export`, the host from the `addr=` option) or the bind mount's host path, read from `/proc/self/mountinfo`. Where that is unknown (not Linux, or the folder is in the container's own layer) the folder's own path is shown.

## Consequences

- Running outside Docker means setting `STAGING_FOLDER` and `LIBRARY_FOLDER` in the start command; moving to another folder needs a restart.
- The mount source is what the container sees; for a bind mount on a filesystem with subvolumes it can differ from the path on the host.
