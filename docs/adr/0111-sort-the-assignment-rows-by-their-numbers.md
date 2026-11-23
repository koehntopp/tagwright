# ADR 0111: A button sorts the assignment rows by their disc and track numbers

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0089](0089-assignment-track-order.md) ("changing a file's release track in the dialog does not reorder the rows")

## Context

0089 lists the rows in the order of the proposed release tracks and keeps that order while the owner edits, so a row does not move under the cursor. After correcting many release tracks and Disc/Track numbers (The Alan Parsons Project, *The Turn Of A Friendly Card*, a Blu-ray with stereo and 5.1 mixes), the rows were still in the old order, and the subtitle dividers, which follow the row order, could not be put where they belong.

## Decision

- The Discogs and MusicBrainz dialogs have a **Sort by disc and track** button beside "Import song titles". It reorders the rows by the Disc and Track numbers as they stand (typed, else the default numbering); skipped files stay last in their order; equal numbers keep their order. The dividers follow the new order.
- Nothing reorders by itself: typing or choosing a release track still leaves the rows where they are (0089).
- The macOS port follows.

## Consequences

- Fix the numbers, press the button, then set the subtitles on the dividers.
