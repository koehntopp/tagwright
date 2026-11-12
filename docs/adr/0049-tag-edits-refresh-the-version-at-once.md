# ADR 0049: Editing format, catalog # or edition refreshes the Discogs tags at once

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0006](0006-status-model-and-pipeline-steps.md) (an edit of `ALBUM_EDITION`, `ALBUM_FORMAT` or `CATALOGNUMBER` leaves the album Ready until the next run)

## Context

`VERSION` (year, DR, format, edition, catalogue number) and the folder name derive from `ALBUM_FORMAT`, `CATALOGNUMBER` and `ALBUM_EDITION`. Changing one of them removed `VERSION`, so "Tags & cover" went grey and the card showed a folder name without the version, until the owner pressed Run fixes. After assigning a release the Discogs tags are already refreshed at once ([0043](0043-assignment-refreshes-the-discogs-tags.md)); the tag editor should behave the same.

## Decision

- Saving the tag editor with a changed `ALBUM_EDITION`, `ALBUM_FORMAT` or `CATALOGNUMBER` on an album with a Discogs release ID removes `VERSION`, writes the other edits, then runs the Discogs tag step (`fix_album`, as the assignment does) so `VERSION` is rewritten before the response. The files are renamed afterwards as always ([0010](0010-bliss-file-naming.md)). The log says "Discogs tags refreshed: ... [version]".
- If the step cannot run (no key, Discogs down) the removed `VERSION` stays removed: "Tags & cover" reopens and the album is Ready until a run, as before, and the log says "not refreshed".
- Saving without such a change does not call Discogs.
- The tag editor closes when Save is pressed and the inspector's step circles spin ([0030](0030-ui-layout-and-design-system-v2.md)): *Tags & cover* and *Filenames* after a format, catalog # or edition edit, *Filenames* alone otherwise, until the server answers. A failed save shows its error as a toast.

## Consequences

- Saving a format or catalogue number edit costs one Discogs request.
- The Tags step is green again after a successful save; the pipeline needs no run for it.
