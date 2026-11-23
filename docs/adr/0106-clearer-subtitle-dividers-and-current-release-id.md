# ADR 0106: Clearer subtitle dividers in the import dialogs; the current release ID in the facts line

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0081](0081-subtitle-dividers-in-track-lists.md) (how an import-dialog divider shows the subtitles) and [0053](0053-discogs-search-and-assignment-consolidated.md) (what the small print under the search field shows)

## Context

The owner found the dividers of the import dialogs hard to read: the release's subtitle in italics ("No subtitle"), a "Was: …" line in tiny grey, and a long "differs from your subtitles" chip, with no label saying which line is which. The small print under the search field (artist, album, year, catalog #) also lacked the release the album has now, which the owner wants to see and copy while searching.

## Decision

- An import-dialog divider (Discogs and MusicBrainz) shows two labelled lines:
  - **Release:** the release's subtitle for the run, or "none"; a yellow **differs** chip when the files' subtitles differ from it.
  - **Current subtitle:** the distinct subtitles the files carry now, or "none".
- The line that will be written is the prominent one, the other is greyed and struck through: with **Release** the release line is dark and the current subtitle struck through; with **Keep mine** the release line is struck through and the current one dark. (Corrected the same day: the first version only greyed the current subtitle under Release.) The Release / Keep mine toggle, the defaults, the pen, the file count and the Disc chip stay as in 0081.
- The Tag Editor's dividers are unchanged (they have no release line).
- The small print under the search field adds the album's current release ID with a copy icon: **Discogs ID** in the Discogs dialog, **MusicBrainz ID** in the MusicBrainz dialog, each only when set.
- The macOS port follows.

## Consequences

- Which subtitle ends up in the files can be read off the divider without knowing the toggle.
