# ADR 0028: rsgain skips an album only when it already has album gain

- **Status**: Accepted
- **Date**: 2026-11-09

## Context

`nzbfix.py` ran `rsgain easy -S` (skip existing, setting `rsgain_skip`). `-S` skips every file that has any ReplayGain tag, so an album with track gain but no `REPLAYGAIN_ALBUM_GAIN` was never scanned and the ReplayGain step ([0006](0006-status-model-and-pipeline-steps.md), which checks `REPLAYGAIN_ALBUM_GAIN`) stayed open (found on `Wham/Last_Christmas_Everything_She_Wants`). The owner agreed to change `nzbfix.py` in the discogs repository ([0004](0004-pipeline-engine-reuses-discogs-scripts.md)).

## Decision

- `nzbfix.py` passes `-S` only when `rsgain_skip` is set **and** every FLAC of the album has `REPLAYGAIN_ALBUM_GAIN`. Otherwise rsgain scans the whole album and writes track and album gain. `mutagen` is added to the script's dependencies for the check.
- Verified on a scratch copy: with track gain only, `-S` writes nothing; without `-S` album gain and peak are written.

## Consequences

- Albums with partial ReplayGain tags are rescanned once; their track gains can change slightly.
