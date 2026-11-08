# ADR 0018: Verification without touching real data

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The app edits and moves real music files. There is no automated test suite; changes have been verified by running the app against copies and driving the UI in a browser.

## Decision

- **Never test against the real library or the real ingest folder.** Copy a small album to a scratch directory outside the library, point `ROOT`, `INGEST_DIR` and `DATA_DIR` at scratch paths, and use a port other than the one the real instance uses.
- Verify behaviour at the API with `curl` and on disk with `metaflac` (tags, pictures), and the UI in a browser at 1440 px width. Confirm the browser console shows no errors.
- A change that alters tag output of the pipeline (DR, fingerprints, ReplayGain) is verified by comparing tags before and after on the same copy; they must be identical.
- Remove scratch data afterwards. Stop test servers.
- Pull in a real Discogs lookup only with the owner's key already configured; never print or commit keys.
- When automated tests are added, they follow this rule and need an ADR for the framework.

## Consequences

- Verification is manual and depends on discipline; this ADR and `AGENTS.md` make it mandatory.
