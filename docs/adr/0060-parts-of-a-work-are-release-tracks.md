# ADR 0060: The parts of a work or medley are release tracks too

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: the tracklist bullet on medleys in [0053](0053-discogs-search-and-assignment-consolidated.md) (from [0046](0046-discogs-medleys-are-one-release-track.md)): "the sub-tracks are not listed ... a medley split into separate files stays a manual choice"

## Context

Discogs lists a work in parts as an `index` entry with sub-tracks: "The Fall Of The House Of Usher (Instrumental)" with I Prelude, II Arrival, III Intermezzo, IV Pavane and V Fall at positions 6 to 10 (release 1545288). The download held one file per part, and with only the entry offered (one track), none of the five files could be assigned.

## Decision

- An `index` entry with sub-tracks stays one release track, as before, so a medley held in one file can be assigned to it. Its duration, when Discogs gives none, is the sum of its parts.
- **Each sub-track is also a release track** (`part_of` names its entry; its position is its own, `6`, `7`, `CD3-6.2`, ...; disc and track number are those of the entry). In the assignment dropdown a part is shown as `↳ title`; in "Not in this album" the parts are not listed, and an entry is not listed when one of its parts is used.
- The proposal fills whole tracks first. The parts then take only the files that are left, and only with a clear title match (a score of 0.45, titles alone reach it when they are close: "Prelude" and "I Prelude"). One release track still cannot be given to two files.
- Because the parts are in the tracklist, `DISCOGS_RELEASE_ORDINAL_POSITION` (the 0-based index in the list) counts them.

## Consequences

- Track counts of a release with such entries are higher than the number of tracks on the disc (12 for release 1545288, where the sleeve says 7).
- A part and its entry can both be chosen by the owner for different files; nothing stops that, only choosing the same one twice is refused.
