# ADR 0046: A Discogs medley is one release track

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0013](0013-discogs-track-assignment.md) (tracklist: "index entries are skipped")

## Context

Discogs lists a medley as an `index` entry (title, duration, no position) with its parts as sub-tracks `CD3-6.1`, `CD3-6.2`, ... The download holds the medley as one file. With index entries skipped, that file had no release track to pick: it could only be set to Skip, and so kept the Discogs release ID of whatever release it had before, leaving the album with two IDs.

## Decision

- An `index` entry with sub-tracks is **one release track**, with the entry's title and duration. Its disc and track number come from the first sub-track's position without the part suffix (`CD3-6.1` is disc 3, track 6). The sub-tracks themselves are not listed.
- After an assignment the log names every skipped file that carries a Discogs release ID other than the chosen one ("X was skipped and keeps Discogs release A, not B"). Skip still leaves the file untouched ([0013](0013-discogs-track-assignment.md)).

## Consequences

- Release track counts (search results, "Not in this album") include medleys as one track.
- A release whose medley is split into separate files is not covered: those files match the sub-track titles only through the medley's title, and stay a manual choice.
