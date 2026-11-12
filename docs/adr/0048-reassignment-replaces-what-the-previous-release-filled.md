# ADR 0048: Re-assigning replaces what the previous release filled

- **Status**: Superseded by [0053](0053-discogs-search-and-assignment-consolidated.md) (consolidated; kept as history)
- **Date**: 2026-11-12
- **Supersedes in part**: [0013](0013-discogs-track-assignment.md) (release-level tags are filled only when empty); extends [0047](0047-a-real-catalogue-number-replaces-none.md)

## Context

The assignment fills album-level tags the old tagger used to import (catalogue number, `ALBUM_FORMAT`, `ALBUMARTIST`, `ALBUM`, the player tags) only when they are empty, so that a value the owner set is never overwritten. After assigning another release, the values filled from the first one stayed (`ALBUM_FORMAT=File` next to a CD release), because the tags were not empty.

## Decision

- When a file's `DISCOGS_RELEASE_ID` differs from the release being assigned, Tagwright computes what the **previous** release would have filled (the same release-level tags, from the previous release's data, fetched and cached). A tag whose current value equals that is replaced by the new release's value. A value that differs from it was set by the owner or a tagger and stays.
- Track-level tags (`ARTIST`, `COMPOSER`, `PRODUCER`, `ENGINEER`) stay fill-when-empty: which track of the previous release a file was cannot be told.
- If the previous release cannot be read (no key, Discogs down), nothing is replaced and behaviour is as before.

## Consequences

- One extra Discogs request per re-assignment (cached afterwards).
- It works from the file's current Discogs ID. Once an assignment has overwritten the ID, the older release is unknown; stale values of an album assigned that way are edited in the tag editor.
