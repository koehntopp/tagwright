# ADR 0039: "Incomplete" instead of "Ready", and showing what is missing

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes**: the label "Ready" of [0006](0006-status-model-and-pipeline-steps.md), [0026](0026-ready-filter-returns.md) and [0030](0030-ui-layout-and-design-system-v2.md) (the status key `ready`, the API and the colours are unchanged)

## Context

"Ready" meant "not blocked, but at least one of the six steps is open"; it read as "ready to move", which is what **Fixed** means. A card only said "Ready" and showed no sign of what was open. In the owner's library 50 of the 51 such albums miss only lyrics (146 tracks, median 2 per album), 2 miss dynamic range; lyrics that lrclib does not have cannot be fixed by a run, other gaps can.

## Decision

- The filter, the status pill and the status names say **Incomplete** (blue, as before). **Needs input** and **Fixed** are unchanged.
- The album summary has `missing`: for every open step the tracks that fail it, `{step, label, count, of, tracks}` (up to 12 track names). Labels: **No lyrics**, **No DR**, **No ReplayGain**, **No fingerprints**, **Tags incomplete**, **Names differ**.
- **Card**: for an Incomplete album the pill on the cover names the first thing that is missing (`No lyrics`, `No DR +1`) instead of the status word; a red badge per missing item with its track count (`No lyrics 2`) sits in a row below the DR and lyrics badges (hover: the track names). This is the red "No lyrics" of 0030, now also for the other steps.
- **Inspector**: a **Missing** box above the pipeline lists each item ("No lyrics on 2 of 4 tracks" and the first track names); clicking one marks those tracks in the track list, as clicking the step does.
- No new filter and no search syntax ([0030](0030-ui-layout-and-design-system-v2.md): the top bar navigation is the only filter).

## Consequences

- A missing item the pipeline cannot fix (lyrics lrclib does not have) stays visible on the card; there is no "accept without lyrics" yet.
