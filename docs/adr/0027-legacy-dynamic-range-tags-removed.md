# ADR 0027: Legacy spaced dynamic-range tags are removed from the discogs scripts

- **Status**: Accepted
- **Date**: 2026-11-09

## Context

[0005](0005-technology-stack-and-conventions.md) says the spaced keys `DYNAMIC RANGE` and `ALBUM DYNAMIC RANGE` are not read by Tagwright. The discogs scripts still accepted them: `calculate_dr.py` counted a track with `DYNAMIC RANGE` as done and never wrote `DYNAMIC_RANGE`, so the DR step ([0006](0006-status-model-and-pipeline-steps.md)) stayed open for such albums (found on `Wham/Last_Christmas_Everything_She_Wants`). The owner asked to remove the code for the old tags (a discogs repository change, [0004](0004-pipeline-engine-reuses-discogs-scripts.md)).

## Decision

- `calculate_dr.py`, `album_list.py`, `fixtags.py` and `webui.py` read only `DYNAMIC_RANGE` and `ALBUM_DR`. A track without `DYNAMIC_RANGE` is recalculated from the audio on the next run.
- Verified on a scratch copy: the old tags stay in the file, `DYNAMIC_RANGE` and `ALBUM_DR` are written.

## Consequences

- Albums that carry only the old tags are recalculated once. Their album DR can change (the old values were not always the current calculation).
