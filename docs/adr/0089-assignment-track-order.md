# ADR 0089: Track order in the assignment dialogs

- **Status**: Accepted (a release track on several discs: [0102](0102-one-release-track-on-several-discs.md); a Sort button: [0111](0111-sort-the-assignment-rows-by-their-numbers.md))
- **Date**: 2026-11-19
- **Supersedes in part**: [0081](0081-subtitle-dividers-in-track-lists.md) (which requires neighbouring tracks to share a disc, but did not say how the rows are ordered)

## Context

The Discogs and MusicBrainz assignment dialogs list the album's files in file order (disc and track number of the files), while the subtitle dividers take the disc and subtitle from the **assigned release track**. When a file's own disc number differs from the release's, the disc chips repeat out of order, for example Disc 2, Disc 1, Disc 2. That contradicts ADR 0081's rule that a multi-disc album has one divider per disc, and makes the list hard to read.

## Decision

- `POST /api/tracks/propose` returns the files sorted by the **assigned release track**: disc, then track number, then the release track's index. Files without an assignment come last, in their original order.
- Both assignment dialogs show that order; it is the order used for the subtitle dividers of [0081](0081-subtitle-dividers-in-track-lists.md) and for applying assignments.
- The order is set when a release is loaded. Changing a file's release track in the dialog does not reorder the rows while the owner is editing. Renumbering still follows [0053](0053-discogs-search-and-assignment-consolidated.md) and [0078](0078-musicbrainz-track-assignment-and-import-song-titles.md) ("1..n per disc in release order"), and no tags are written by the sort.

## Consequences

- A multi-disc release shows Disc 1 tracks together before Disc 2 tracks, with one divider per disc as ADR 0081 intends.
- A file whose tags disagree with the release is placed where the release says it belongs, which also makes the mismatch visible.
- Unassigned ("Skip") files collect at the end of the dialog.
