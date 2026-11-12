# ADR 0068: Playback can always be stopped

- **Status**: Accepted
- **Date**: 2026-11-13
- **Supersedes in part**: [0015](0015-track-playback-and-track-edit.md) (the play button of the track list is the only control)

## Context

One audio player serves the whole page, and its only control was the play button in the track list of the selected album. When the playing album was moved (the watcher puts a corrected artist name in another folder), the album left the board, its track list was gone and nothing could stop the track.

## Decision

- While a track plays, the top bar shows a **Stop** button (the animated bars and "Stop", left of Settings). It stops the player and releases the file, whatever album is selected or whether the album still exists.
- When the album of the playing track is no longer in the album list (moved, removed), playback stops by itself.
- The play button of a track and the animated bars on the album's card work as before.
