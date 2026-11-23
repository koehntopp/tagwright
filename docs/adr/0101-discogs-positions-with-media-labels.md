# ADR 0101: Disc and track from Discogs positions with media labels

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) (the rule "Position `D-T` or `CDD-T` gives disc and track ...")

## Context

Billy Joel, *Piano Man* (2024, Discogs 29934862) is an SACD + CD + DVD set. Discogs numbers its tracks `SACD-1` … `SACD-10`, `CD-1` … `CD-16`, `DVD-1` … `DVD-11`, under the headings `Disc 1 (SA-CD): …`, `Disc 2 (CD): …`, `Disc 3 (DVD): …`. The rule of 0053 reads only `D-T` and `CDD-T` (and `DVDD-T`), so every track of this release was disc 1, numbered 1 to 37 through the whole release. The SACD files were proposed correctly only because that disc comes first; the CD files would have been proposed as disc 1, tracks 11 to 26, and the proposal's "same disc and track" bonus never applied to them. Discogs uses the same style for Blu-ray (`BD-1`, `BD1-1`), SACD (`SACD1-1`) and other media in mixed-format sets.

## Decision

Positions are read in tracklist order (`pipeline/positions.py`, used by the assignment; the macOS port has the same rule):

- `D-T` or `D.T`, with or without a media label of two or more letters in front (`1-3`, `2.3`, `CD2-3`, `SACD1-4`, `BD1-2`, `HDCD1-3`): disc D, track T.
- A media label without a disc number (`SACD-1`, `CD-1`, `DVD-1`, `BD3`): track T on the disc of the last heading that names one; without such a heading, every new label is the next disc after the highest so far (`SACD-n` disc 1, `CD-n` disc 2; after `CD1-n`, `CD2-n` a `DVD-n` is disc 3).
- A plain number under a heading that names a disc: track T of that disc, as before.
- A heading names a disc when it starts with `Disc`, `Disk`, `CD`, `SACD`/`SA-CD`, `HDCD`, `DVD`, `BD` or `Blu-ray` and a number (`Disc 2 (CD): …`, `SACD 1`). That label is stripped from the subtitle as before ([0081](0081-subtitle-dividers-in-track-lists.md)).
- Everything else (vinyl `A1`, plain numbers without such a heading, empty) is numbered in sequence on disc 1, as before. A one-letter label is a vinyl side, never a media label.

Video discs stay release tracks: the default numbering counts only the discs that have assigned files (0053), so assigning the SACD and the CD of the set above gives discs 1 and 2.

## Consequences

- Mixed-format box sets get the disc numbers Discogs means; the proposal's disc/track bonus works on them.
- A release that writes a media label for a single disc and something else for its other discs may still need the Disc and Track fields corrected by hand, as before.
- `scripts/fix-credits.py` matches files by `TRACK_NUMBER_TEXT`, ordinal and title, not by these numbers; it is not affected.
