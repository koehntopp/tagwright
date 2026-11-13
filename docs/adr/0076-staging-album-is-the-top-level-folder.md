# ADR 0076: In the staging folder, a top-level folder is one album

- **Status**: Accepted
- **Date**: 2026-11-13
- **Supersedes in part**: [0054](0054-album-status-and-steps-consolidated.md) (the "Album folders" rule), for the staging folder

## Context

The rule of 0054 groups only `Disc N` / `CD N` subfolders (exact names) with their parent. A downloaded box set with folders named `Disc 1 - Nebraska Outtakes`, `Disc 2 - Electric Nebraska` and so on showed as four albums. The owner treats every top-level folder of a download as one album.

## Decision

- **In the staging folder** every folder directly below it is one album, if it holds audio anywhere below it. Its tracks are all audio files below it, at any depth, whatever the subfolders are called. Hidden folders and files are skipped as before; the staging folder itself is never an album; a folder without audio is not listed.
- **Everywhere else** (the library, where the layout is `Artist/Album[/Disc N]`) the rule of 0054 stays: the album's own files plus its `Disc N` / `CD N` folders; other subfolders are other albums.
- The dynamic range step runs `drcalc --album overall` on the album folder, so `ALBUM_DR` is the mean over every file of the album whatever the disc folders are called. For `Disc N` layouts the result is the same as with `--album folder`.
- The ReplayGain step is unchanged: `rsgain easy` treats every folder as one album, also `Disc 1` / `Disc 2` (measured on scratch files: each disc gets its own album gain). Tagwright does not change that here.
- The pipeline package learns the staging folder through `pipeline.layout.STAGING`, set by the web layer at start-up.

## Consequences

- A collection folder that holds several albums in subfolders (`staging/Artist/Album 1`, `staging/Artist/Album 2`) is one album. Move them up to the top level of staging, one folder per album.
- The album's move to the library places every file by its tags (`DISCNUMBER`), so a box with free-form disc folder names lands in the library's `Disc N` folders ([0037](0037-library-watcher-and-layout.md)).
- A staging album can now have audio at several depths; summaries and signatures use the same file list, so nothing else changes.
