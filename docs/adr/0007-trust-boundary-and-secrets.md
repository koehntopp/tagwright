# ADR 0007: Trust boundary, no authentication, secrets

- **Status**: Accepted (`safe()` also accepts the library folder: [0038](0038-staging-and-library-views.md))
- **Date**: 2026-11-08

## Context

The app can rewrite tags, rename files and move folders on a server, and stores API keys. It is for one person on a home network.

## Decision

- **No authentication and no TLS in the app.** It must run behind a reverse proxy or on a trusted network. It must not be exposed to the internet as is.
- **Path guard**: every endpoint that takes a path resolves it and requires it to be `ROOT` or below (`safe()`); a path outside returns 400. A file inside an album is addressed as `<album path>` plus a relative `file`, and the combination is checked again by `safe()`; only `.flac` files are served or edited by that route.
- **Writes only through documented endpoints** ([0008](0008-job-model.md) rule: refused while a job runs).
- **Secrets**: API keys live in `DATA_DIR/settings.json`, file mode `0600`, in plain text. The settings endpoint never returns a key, only the last four characters as a hint. Keys are never logged and never written to a file other than `settings.json` and the generated overlay ([0009](0009-settings-and-api-keys.md)). `data/` is git-ignored.
- **No outbound calls** except Discogs (track editor), lrclib.net ([0021](0021-lrclib-lyrics-search.md)), MusicBrainz ([0023](0023-musicbrainz-release-search.md)) and whatever the discogs scripts do (Discogs, MusicBrainz, lrclib, AcoustID).

## Consequences

- Anyone who can reach the port can edit the library. Network placement is the access control.
- Plain-text keys are accepted because the data directory is a private mount; moving to a secret store needs a new ADR.
