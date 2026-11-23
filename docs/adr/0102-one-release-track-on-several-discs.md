# ADR 0102: One release track on several discs of the album

- **Status**: Accepted (more album discs than release discs also number each album disc on its own: [0109](0109-proposal-keeps-album-discs-together-and-matches-medley-parts.md))
- **Date**: 2026-11-23
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) (a release track goes to one file only; the proposal's scoring and numbering), [0060](0060-parts-of-a-work-are-release-tracks.md) ("only choosing the same one twice is refused"), [0081](0081-subtitle-dividers-in-track-lists.md) (the disc a divider names), [0089](0089-assignment-track-order.md) (the order of the rows)

## Context

A Blu-ray often holds the same songs in three or four mixes (Atmos, 5.1, stereo, the original mix). Discogs may list the songs only once per group of mixes: Phil Collins, *Face Value* (2026, Discogs 38461926) has 24 tracks, 1-12 under one heading for the 2026 Atmos, stereo and 5.1 mixes, 13-24 under "Original 1981 Stereo Mix". The album has 48 files on four discs: discs 1-3 are tracks 1-12, disc 4 is tracks 13-24. The assignment refused a release track on more than one file, so only 24 files could be assigned, and the proposal left the rest on Skip.

## Decision

- **A file's own disc** is the leading number of its `DISCNUMBER` when the dialog opens (disc 1 without one).
- **A release track may go to one file per disc of the album.** The same release track twice among the files of one disc is refused, in the dialog (red border, Apply disabled, "A release track is assigned to more than one file of the same disc.") and by both apply endpoints (400 "a release track is assigned twice on one disc").
- **Numbering**: when no release track is used twice, it stays as in 0053 (1..n per disc of the release, in release order over the selected files). When one is, every disc of the album is numbered on its own: discs in the order (disc of the album, disc of the release), renumbered from 1, tracks 1..n in release order. Disc and Track stay editable.
- **Proposal** (`POST /api/tracks/propose`):
  - Scores as in 0053, plus, only for a release track whose title the release lists more than once, the share of the words of the file's subtitle (`SET SUBTITLE`/`DISCSUBTITLE`) found in the track's subtitle × 0.3, so each mix picks the songs of its own heading.
  - After the passes of 0053 and 0060, files still unassigned may take a release track that a file of another disc already has, on a score of at least 0.6.
  - When a release track is used twice, the rows are listed by release disc, then disc of the album, then track.
- **Dividers** name the disc the files will get (the Disc field, else the default numbering), so every disc of the album gets its own divider.
- The "Apply (n of m)" count is the number of assigned files.

## Consequences

- *Face Value* is proposed and written as the owner wants: discs 1-3 tracks 1-12 with release tracks 1-12, disc 4 tracks 1-12 with release tracks 13-24, every file keeping its own subtitle.
- An album whose files carry wrong disc numbers may now be offered a release track twice (on two "discs") where before the second file stayed on Skip; the 0.6 threshold keeps that to clear title matches.
- The macOS port follows the same rule.
