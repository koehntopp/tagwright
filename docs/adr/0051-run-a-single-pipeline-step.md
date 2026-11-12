# ADR 0051: A double click on a pipeline step runs only that step

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0036](0036-standalone-pipeline-package.md) (the six steps are always one run, none skipped)

## Context

After fixing one thing (a new lyrics source, a replaced cover, a changed Discogs release) the owner wants to redo one step without waiting for the dynamic range and ReplayGain of a whole album again.

## Decision

- Double-clicking a step in the inspector's pipeline row runs **only that step** on the album. `POST /api/run` takes an optional `step` (the UI step name: Dynamic range, ReplayGain, Fingerprints, Tags and cover, Lyrics, Filenames); without it nothing changes and the whole pipeline runs in its fixed order. An unknown name answers 400.
- Tags and cover runs the Discogs tags step, Filenames runs only the rename. The file rename that ends a run also ends a run of Tags and cover or Filenames, and is not done after the others.
- The same rules apply as for a full run: one job at a time (409), the step circle spins while it runs ([0030](0030-ui-layout-and-design-system-v2.md)), the log and Stop work as before ([0008](0008-job-model.md)). The button **Run fixes** still runs everything.
- **Dynamic range, ReplayGain and Fingerprints measure the sound** and need no tags, so they also run on an album that *needs input* (for example one without a Discogs release yet). The other steps are refused for such an album (409), as is a full run.
- A single click still selects the step and marks its tracks in the track list. Each step's tooltip says "Double-click to run only this step."

## Consequences

- The order rule of [0036](0036-standalone-pipeline-package.md) holds inside a run; running one step is the only way to skip the others.
