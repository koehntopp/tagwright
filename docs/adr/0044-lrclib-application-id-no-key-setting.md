# ADR 0044: lrclib.net is reached with the application ID; no key setting

- **Status**: Accepted
- **Date**: 2026-11-11
- **Supersedes in part**: [0009](0009-settings-and-api-keys.md) (the lrclib.net API key setting) and [0021](0021-lrclib-lyrics-search.md) (the search without the application ID)

## Context

lrclib.net lets a registered application identify itself with the public `Lrclib-App-Id` header, which raises the rate limit. The ID is not a secret. The pipeline already sent it ([0036](0036-standalone-pipeline-package.md), `pipeline/lrclib.py`), while the track editor's search sent only a user agent. The Settings dialog also offered an optional lrclib.net API key that nothing read.

## Decision

- Every request to lrclib.net, the pipeline's lookup and the editor's search, sends the user agent and the registered application ID from `pipeline/lrclib.py`. The search endpoint reuses `lrclib.headers()`.
- The lrclib.net API key setting is removed: no field in Settings, no `lrclib_api_key` in `settings.json` (a stored value is dropped on the next save), no hint in `GET /api/settings`. The secret `Lrclib-Api-Key` header stays unused.
- The application ID is committed in code. It is public by lrclib's own definition; the rule against committing API keys ([0007](0007-trust-boundary-and-secrets.md)) is about secrets and does not apply.

## Consequences

- One less thing to configure; Settings holds only the Discogs key.
- UC-1 no longer mentions an lrclib key.
