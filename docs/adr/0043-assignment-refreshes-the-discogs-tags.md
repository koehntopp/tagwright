# ADR 0043: Assigning a Discogs release refreshes the Discogs-owned tags at once

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes**: the part of [0013](0013-discogs-track-assignment.md) that leaves the Discogs-owned tags (year, album title, version, label ...) to the next run

## Context

After assigning another Discogs release the files kept the previous release's year, album title and version until **Run fixes**. The card and the inspector read those tags, so they showed the old data next to the new release ID, and the MusicBrainz year note compared with the old year.

## Decision

- Applying an assignment writes the release ID, the track numbers and titles and the tags that are filled when empty (as before), then runs the **Discogs tags step** of the pipeline ([0036](0036-standalone-pipeline-package.md), `pipeline.fixtags.fix_album`) on the album, then renames the files. The step writes exactly what a run writes (year, original year, album title, version, label, catalogue and the other `ALBUM_*` tags, cover resize); it needs three Discogs requests.
- Nothing else of the pipeline runs: no DR, ReplayGain, fingerprints or lyrics.
- A Discogs or MusicBrainz failure in that step does not fail the assignment: the log says "Discogs tags not refreshed: <reason>" and Run fixes does it later.
- Tags the user owns (album artist and title overrides, format, edition) are untouched, as in a run.

## Consequences

- The card, the inspector, the folder line and the year note show the new release immediately after Apply.
- An assignment needs the Discogs API key for this step; without it the log says so and the rest is done.
