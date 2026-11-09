# ADR 0015: Track playback and per-track edit

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

UC-8. Checking a track by ear and fixing its title or lyrics should not need another application.

## Decision

- **Track list** (inspector "Tracks" box, one row per file): round play/pause button, track number, title, length (m:ss), per-step check mark when a pipeline step is selected, DR badge, lyrics badge, round pen button. Length, DR and lyrics badges have fixed widths so columns align (a "No lyrics" badge must not shift the others).
- **Playback**: `GET /api/audio?path=&file=` serves the FLAC file (`FileResponse`, range requests). The browser plays it in one shared `Audio` element; starting another track stops the current one; the icon toggles play/pause; the end of a track resets it. Playback is in the browser, not on the server. Browsers must support FLAC (current Chrome, Firefox, Safari do).
- **Edit**: the pen opens a dialog with title, artist and lyrics (monospace textarea, synced `[mm:ss.xx]` or plain). `GET /api/track` reads, `POST /api/track` writes `TITLE` and `ARTIST` (neither may be empty) and `LYRICS` (empty removes the tag), then renames the file ([0010](0010-bliss-file-naming.md)). Refused while a job runs.
- **Marker buttons** in the lyrics field of the edit dialog:
  - **Instrumental** replaces the whole field with `[00:00.00] [Instrumental]`.
  - **Spoken Intro** replaces the whole field with `[00:00.00](Spoken Intro)`.
  Both clear the existing lyrics first and only change the text field; nothing is stored until Save (Cancel keeps the old lyrics). `update_lyrics.py` normalises the instrumental marker into its canonical block on its next run; the spoken-intro line is an ordinary synced line.
- The lyrics header also has a **Search lrclib.net** button ([0021](0021-lrclib-lyrics-search.md)).
- Lyrics are written as a single `LYRICS` value, the tag `update_lyrics.py` and the status model use ([0006](0006-status-model-and-pipeline-steps.md)). Editing lyrics does not set or clear `LYRICS_LANGUAGE`.

## Consequences

- A hand-edited lyric that is plain text shows as TXT (yellow step). Synced lyrics stay the pipeline's job.
