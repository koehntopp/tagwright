# ADR 0052: The Discogs search starts with artist and album and marks MusicBrainz matches

- **Status**: Superseded by [0053](0053-discogs-search-and-assignment-consolidated.md) (consolidated; kept as history)
- **Date**: 2026-11-12
- **Supersedes in part**: [0013](0013-discogs-track-assignment.md) (the search field is prefilled with the album's Discogs ID)

## Context

Opening the assignment dialog on an album that already had a Discogs ID put that ID in the search field, so a new search could only find the same release again. The MusicBrainz dialog already starts with artist and album ([0023](0023-musicbrainz-release-search.md)). When the album has a MusicBrainz release, that release's Discogs links tell which Discogs release is the right one.

## Decision

- The search field of the assignment dialog always starts with **artist and album**. An album with a Discogs ID still opens with that release loaded below.
- Under the field, small print shows the album's artist, album, year and catalog # (when set), each with a copy icon, as in the MusicBrainz dialog.
- `GET /api/discogs/search` takes the album `path`. When the album has a `MUSICBRAINZ_ALBUMID` and that MusicBrainz release links Discogs releases (`discogs_ids`, [0023](0023-musicbrainz-release-search.md)), the results that are among them come first with `match: 'MusicBrainz'`, shown as the badge **MusicBrainz match**. MusicBrainz being unreachable only drops the badge.

## Consequences

- One extra MusicBrainz request per search when the album has a MusicBrainz ID (cached afterwards).
