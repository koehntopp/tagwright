# ADR 0058: Audio files are opened through one seam

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

Tagwright reads and writes tags with `mutagen.flac.FLAC` in about 30 places in `app.py`, `pipeline/` and `library/`, and tests the extension `.flac` in several more. Supporting another format (MP3 is the next one) would otherwise mean touching all of them at once.

## Decision

- `pipeline/audio.py` is the only module that imports a format class from mutagen. Everything else calls `open_audio(path)`, works on the `Audio` interface (mutagen's FLAC surface: a case-insensitive dict of lists in `.tags`, `.pictures`, `add_picture`, `clear_pictures`, `.info`, `save`) and builds covers with `new_cover()` (type `Cover`). File names are accepted by `is_audio(name)`, which today means the extension `.flac` in any case. `EXTENSIONS` is the one list.
- This was a refactor: behaviour unchanged, only FLAC handled. Another format provides the same `Audio` surface: MP3 does, see [0059](0059-mp3-support.md). `EXTENSIONS` is `.flac` and `.mp3`.
- Names produced by Tagwright follow the file's own extension ([0059](0059-mp3-support.md)).

## Consequences

- One place to change when a format is added. Tests still create files with mutagen directly; that is test setup, not program code.
