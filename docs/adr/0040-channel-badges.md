# ADR 0040: Channel badges (Mono, Stereo, 5.1, 7.1) on tracks

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

One album can hold the same song in several mixes (stereo and 5.1, mono and stereo). The track lists did not say which file is which, and assigning files to a Discogs or MusicBrainz track list by title alone mixed them up.

## Decision

- Every track row shows a badge for its channel layout: **Mono** (1 channel), **Stereo** (2), **5.1** (6), **7.1** (8); other counts show 3.0, 4.0, 5.0 or 6.1 (3, 4, 5, 7 channels), anything else `N ch`. The count is read from the FLAC stream (`channels`), never from a tag.
- **Colour**: Mono and Stereo are neutral grey; multichannel (more than 2) is violet. This is a new meaning ("more than stereo") and uses a colour no other badge has ([0030](0030-ui-layout-and-design-system-v2.md)). The badge has a fixed width so rows stay aligned.
- **Where**: the inspector's track list; the Tag editor's Tracks tab (a Channels column, read-only); the Discogs assignment dialog (on each file); the MusicBrainz release dialog (on each release track).
- **Release tracks** (Discogs, MusicBrainz) have no channel field. The badge there is a hint taken from the title (`5.1`, `7.1`, `Mono`, `Stereo` as separate words, so `Monologue`, `15.1` and `5.10` do not match), drawn paler and labelled "The title says ...". The Discogs track picker appends the layout to a title that names one.
- The API carries `channels` on the album summary's `files`, on `/api/tags` tracks, on `album_files` and, as a hint, on the release tracks.
- Nothing is written to tags; the tag editor's save ignores the column.

## Consequences

- Files of one title in different mixes can be told apart in every list.
- A release that does not name the mix in its titles shows no hint; the file's own badge is the reference.
