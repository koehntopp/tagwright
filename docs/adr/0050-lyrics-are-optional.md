# ADR 0050: Missing lyrics are an optional, blue notice

- **Status**: Superseded by [0054](0054-album-status-and-steps-consolidated.md) (consolidated; kept as history)
- **Date**: 2026-11-12
- **Supersedes in part**: [0006](0006-status-model-and-pipeline-steps.md) (`fixed` needs all six steps), [0039](0039-incomplete-albums-and-missing-lists.md) (every open step is a red "missing" entry)

## Context

Some tracks have no lyrics anywhere: a medley, a spoken intro, a remix that lrclib does not know. One such track kept a 35-track album at `ready` and the Move to library button disabled, although nothing else was open.

## Decision

- The Lyrics step is **optional**. An album is `fixed` when every step except Lyrics is done. The step's circle still shows open, and the lyrics count and the TXT/LRC badges are unchanged.
- "No lyrics" is still listed per track, but as an **optional** entry: a blue pill on the card (red for the required steps) and a blue **Optional** box in the inspector, separate from the red **Missing** box. The summary's `missing` entries carry `optional: true`.
- An album with only lyrics open is `fixed`, so **Move to library** is enabled ([0011](0011-ingestion-move.md)). The card's status badge names the first *required* missing step, never lyrics.
- Run fixes keeps trying the lyrics step as before.

## Consequences

- The "accept without lyrics" mark offered earlier is not needed.
- Albums in the library that lack lyrics show as `fixed` with a blue notice.
