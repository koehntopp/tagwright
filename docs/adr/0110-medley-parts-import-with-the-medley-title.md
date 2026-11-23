# ADR 0110: Medley parts are imported with the medley's title

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0060](0060-parts-of-a-work-are-release-tracks.md) (a part's title is its own title everywhere)

## Context

With "Import song titles" on, a file assigned to a part of a medley got the part's own Discogs title: "Prelude" for a file titled "The Fall Of The House Of Usher (Prelude)" (The Alan Parsons Project, *Tales Of Mystery And Imagination*), and the file was renamed `01_06_Prelude.flac`. The part alone does not say which work it belongs to. The owner wants the full title.

## Decision

- The title a release track gives a file (the prefilled, editable title in the Discogs and MusicBrainz dialogs, and the TITLE written when nothing was typed) is `Medley (Part)` for a part, for example "The Fall Of The House Of Usher (Prelude)"; whole tracks keep their title. Server: `import_title`; dialog: `importTitle`.
- The dropdown keeps showing a part as `↳ Prelude` under its medley (0060); "Not in this album" is unchanged.
- The macOS port has no part tracks yet (its GAPS), so nothing changes there.

## Consequences

- File names follow: `01_06_The_Fall_Of_The_House_Of_Usher_Prelude.flac`.
