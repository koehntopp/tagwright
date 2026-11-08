# ADR 0004: The pipeline engine is the unchanged discogs scripts

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The `discogs` repository already implements the fix pipeline and its tag contract (its own ADRs, notably 0002 "FLAC tag handling", govern it). Rewriting it in another language was considered and rejected for now ([0012](0012-language-and-performance.md)).

## Decision

- "Run fixes" runs `nzbfix.py <album path>` from `DISCOGS_DIR` as a subprocess (`cwd=DISCOGS_DIR`, `LOG_LEVEL=INFO`), streaming stdout/stderr into the job log.
- `nzbfix.py` runs `dot_clean`, then `calculate_dr`, `rsgain` and `calculate_fp` in parallel, then `fixtags` and `update_lyrics`. Tagwright does not reimplement, reorder or skip any of these.
- Tagwright **never changes the discogs scripts' behaviour from outside**. Changes to pipeline logic are made in the discogs repository under its own ADRs.
- Tagwright reads and writes FLAC tags itself only for the features in [0013](0013-discogs-track-assignment.md), [0014](0014-internal-tag-editor.md), [0015](0015-track-playback-and-track-edit.md), [0016](0016-cover-art.md), and the file rename in [0010](0010-bliss-file-naming.md). All such writes obey the discogs tag contract: uppercase keys, no tool-written tag read back as input, user-set tags are never overwritten by automation.
- After `nzbfix` exits with code 0, Tagwright renames the files ([0010](0010-bliss-file-naming.md)).
- API keys reach the scripts through a generated config overlay ([0009](0009-settings-and-api-keys.md)).

## Consequences

- Tagwright needs a discogs checkout at `DISCOGS_DIR` and `uv` to run its scripts.
- Tagwright's list of "tags Discogs writes" ([0014](0014-internal-tag-editor.md)) mirrors `fixtags.py` and must be kept in sync by hand.
