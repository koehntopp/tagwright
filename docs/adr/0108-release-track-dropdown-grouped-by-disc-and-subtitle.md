# ADR 0108: The release-track dropdown is grouped by disc and subtitle

- **Status**: Accepted
- **Date**: 2026-11-23

## Context

In the Discogs and MusicBrainz assignment dialogs, each file's **Release track** dropdown listed every track of the release as "position title (duration)". On a release with the same songs in several mixes (The Alan Parsons Project, *Tales Of Mystery And Imagination*, Discogs 9448188: tracks 1-12 the 5.1 mix with Orson Welles, 13-24 the original 1976 stereo mix) the entries could not be told apart without counting. The owner asked for indicators of the disc and the subtitle.

## Decision

- The dropdown's entries are grouped in runs of neighbouring release tracks with the same disc and subtitle (the subtitle of [0081](0081-subtitle-dividers-in-track-lists.md)), each under a non-selectable header **Disc N · subtitle** (or **Disc N** without one): `<optgroup>` on the web, menu sections in the macOS port.
- A release with one disc and no subtitles keeps the plain list without headers. "Skip (leave as is)" stays first, outside the groups.
- The entries themselves are unchanged.

## Consequences

- Choosing between the mixes of a multi-mix release is a matter of reading the header.
