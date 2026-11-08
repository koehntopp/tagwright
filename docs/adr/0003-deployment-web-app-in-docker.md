# ADR 0003: Deployment: a web app in Docker on a Linux server

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The first idea was a native macOS app. The pipeline needs `rsgain`, Python tools, `fpcalc`, `flac` and long-running work on a large library that lives on a NAS share. A native app would have to bundle or locate all of these on a Mac, and the work should run next to the files.

## Decision

- Tagwright is a **web app served by a Linux server**, packaged as a Docker image (`Dockerfile`, `compose.yaml`). The browser is the only client.
- The image holds Python 3.14 (the version the discogs scripts target), `uv`, `flac`, `chromaprint-tools` (`fpcalc`). `rsgain` and `drmeter` binaries are expected in `./bin/` of the build context (not committed; they have no apt packages).
- Mounts: input folder at `/staging`, ingest folder at `/flac/ingest`, a checkout of the discogs repo read-only at `/opt/discogs`, and `./data` at `/data` for settings.
- The same code runs directly on macOS for development: `ROOT=... INGEST_DIR=... DISCOGS_DIR=... ./app.py` (shebang `uv run`).
- Environment: `ROOT`, `INGEST_DIR`, `DISCOGS_DIR`, `DATA_DIR`, `PORT` (default 8080). Paths must be absolute; `~` is expanded by the app but a relative path is a startup error.

## Consequences

- Anything the browser needs from the filesystem goes through the API (covers, audio). Paths shown in the UI are server paths; the UI never assumes they exist on the client. This is why the external-editor link (a `yate://` URL with a client-side path mapping) was removed in favour of the internal tag editor ([0014](0014-internal-tag-editor.md)).
- The Docker image has not been built or run end to end; the `bin/` binaries are a manual prerequisite.
