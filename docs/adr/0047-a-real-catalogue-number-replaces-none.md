# ADR 0047: A real catalogue number replaces the placeholder `none`

- **Status**: Superseded by [0053](0053-discogs-search-and-assignment-consolidated.md) (consolidated; kept as history)
- **Date**: 2026-11-12
- **Supersedes in part**: [0013](0013-discogs-track-assignment.md) (the catalogue number is filled only when the tag is empty)

## Context

`none` is the placeholder for "this release has no catalogue number" ([0013](0013-discogs-track-assignment.md), [0014](0014-internal-tag-editor.md)). Files tagged earlier, for example from a digital edition, carry `CATALOGNUMBER=none`. Assigning a Discogs release that has a real number (Cherry Pop `QCRPOPX230`) left `none` in place, because the tag was not empty, so the card kept showing "File (none)".

## Decision

- On assignment, when the release has a real catalogue number (not `none`) and a file's catalogue number, under any of the four spellings, is `none` (any case), that tag is removed and the release's number is written. Any other existing value is still never overwritten.
- `ALBUM_FORMAT` and the other fill-when-empty tags are unchanged.

## Consequences

- The next refresh of the Discogs-owned tags ([0043](0043-assignment-refreshes-the-discogs-tags.md)) rebuilds `VERSION` from the new number.
- Albums assigned before this change keep `none` until the release is assigned again or the number is edited in the tag editor.
