# ADR 0006: Status comes from FLAC tags; six pipeline steps

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The UI must show what an album still needs. The discogs pipeline records its results as tags in the files, and external taggers change tags too. A separate database would drift from the files.

## Decision

### The files are the single source of truth

No state is stored besides settings ([0009](0009-settings-and-api-keys.md)). Everything shown is derived from the FLAC tags and stream info by `summarize(album)`.

### Album folders

An album is a folder that contains FLAC files. Folders named `Disc N` or `CD N` (any case) are grouped into their parent so a multi-disc album is one album. `ROOT` itself is never an album.

### Six steps (in pipeline order)

| Step | Done when |
|------|-----------|
| Dynamic range | every track has `DYNAMIC_RANGE` |
| ReplayGain | every track has `REPLAYGAIN_ALBUM_GAIN` |
| Fingerprints | every track has `ACOUSTID_FINGERPRINT` |
| Tags and cover | a `DISCOGS_RELEASE_ID` exists, every track has `ARTIST`, `TITLE`, `ALBUM`, `TRACKNUMBER` and `DATE` or `YEAR` |
| Lyrics | no track is missing lyrics (see below) |
| Filenames | every file name equals the bliss name of its tags ([0010](0010-bliss-file-naming.md)) |

A step may be **done but partial** (shown yellow, still counts as done):
- Lyrics: at least one track has plain-text (not synced) lyrics.
- Tags and cover: the cover is smaller than 1400x1400 or missing ([0016](0016-cover-art.md)).

Lyrics kinds per track, checked in this order (the same rule as the discogs `lrc_count.py`, which this mirrors):
1. Empty `LYRICS`: `instr` if `LYRICS_LANGUAGE` is `zxx`, else `none`.
2. `instr` (shown as **Instrumental**): the text contains the canonical sentinel `[instrumental:true]`, or a hand-typed marker `[MM:SS.xx][Instrumental]` / `[MM:SS.xx](Instrumental)` (case-insensitive, optional whitespace between the parts; `update_lyrics.py` rewrites these into the canonical block on its next run).
3. `lrc` (synced): contains a strict timestamp `[MM:SS.xx]` (two digits each).
4. `txt`: any other non-empty text.

A track is "missing" only when it is `none`. Any non-empty lyrics, synced, plain or instrumental, satisfy the step. The instrumental block itself contains `[00:00.00]`, which is why `instr` is tested before `lrc`.

### Album status

- `needs`: no `DISCOGS_RELEASE_ID` (fixtags cannot run without it).
- `fixed`: all six steps done.
- `ready`: everything else.

### Displayed values

Album DR is `ALBUM_DR`, falling back to the rounded mean of the track `DYNAMIC_RANGE` values. Artist is `ALBUMARTIST`, else `ARTIST`. "New folder" shows the bliss library path `<album artist>/<album [version]>` for information only; Tagwright does not rename album folders ([0010](0010-bliss-file-naming.md)).

### Scan cache

Per album, `summarize` results are cached in memory keyed by the signature `(file name, mtime_ns, size)` of all its files; any change by Tagwright or an external tagger changes the signature and invalidates the entry. Albums are scanned with 8 worker threads. The cache is cleared when the input folder changes.

## Consequences

- External edits are seen on the next list load or refresh (no filesystem watcher yet; automatic re-scan was proposed, not built).
- The status model must change together with `nzbfix.py` if the pipeline gains or loses a step.
