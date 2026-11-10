# ADR 0015: Track playback and per-track edit

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

UC-8. Checking a track by ear and fixing its lyrics should not need another application.

## Decision

- **Track list** (inspector "Tracks" box, one row per file): round play/pause button, track number, title, length (m:ss), per-step check mark when a pipeline step is selected, DR badge, lyrics badge, round pen button. Length, DR and lyrics badges have fixed widths so columns align (a "No lyrics" badge must not shift the others).
- **Playback**: `GET /api/audio?path=&file=` serves the FLAC file (`FileResponse`, range requests). The browser plays it in one shared `Audio` element; starting another track stops the current one; the icon toggles play/pause; the end of a track resets it. **The playing track is marked**: its row in the track list gets a yellow bar on the left and a light yellow background, and the album's card shows an animated yellow equalizer badge at the top right of the cover (also while another album is selected). The playing state is kept for the whole page, not per inspector. Playback is in the browser, not on the server. Browsers must support FLAC (current Chrome, Firefox, Safari do).
- **Edit**: the pen opens a dialog (file name and length in the header) with the lyrics (monospace textarea, synced `[mm:ss.xx]` or plain) and two search fields, title and artist, prefilled from the tags and used only for the lrclib.net search ([0021](0021-lrclib-lyrics-search.md)). `GET /api/track` reads, `POST /api/track` writes **only `LYRICS`** (empty removes the tag); the search fields are never written back and never block saving (a track with an empty `ARTIST` can still be saved). Title and artist are edited in the tag editor's Tracks tab ([0014](0014-internal-tag-editor.md)), which also renames the files ([0010](0010-bliss-file-naming.md)). Refused while a job runs.
- **Marker buttons** in the lyrics field of the edit dialog:
  - **Instrumental** replaces the whole field with `[00:00.00] [Instrumental]`.
  - **Spoken Intro** replaces the whole field with `[00:00.00](Spoken Intro)`.
  Both clear the existing lyrics first and only change the text field; nothing is stored until Save (Cancel keeps the old lyrics). `update_lyrics.py` normalises the instrumental marker into its canonical block on its next run; the spoken-intro line is an ordinary synced line.
- Layout: a shaded search bar (Title and Artist inputs, Enter in either starts the search, and the **Search lrclib.net** button, [0021](0021-lrclib-lyrics-search.md)) above the lyrics. The lyrics header shows a fixed-width format badge (LRC green, TXT yellow, Empty grey, the same names as the track list) and a line count, updated as the text changes; the marker buttons are ghost buttons. The results box has a sticky count header, and results whose length is within 3 s of the file have a light green background, and the result last used has a ring. Times (the track length in the header, the result lengths) are grey badges, so they read as the same quantity; the result buttons use the list colours (LRC green, TXT yellow).
- Lyrics are written as a single `LYRICS` value, the tag `update_lyrics.py` and the status model use ([0006](0006-status-model-and-pipeline-steps.md)). Editing lyrics does not set or clear `LYRICS_LANGUAGE`.

## Consequences

- A hand-edited lyric that is plain text shows as TXT (yellow step). Synced lyrics stay the pipeline's job.
