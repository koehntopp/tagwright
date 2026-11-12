# ADR 0006: Status comes from FLAC tags; six pipeline steps

- **Status**: Accepted (lyrics are optional: [0050](0050-lyrics-are-optional.md); an edit of format, catalog # or edition refreshes `VERSION` at once instead of leaving the album Ready: [0049](0049-tag-edits-refresh-the-version-at-once.md)) (the label "Ready" is now "Incomplete" and, without a Discogs release ID, the red Discogs line is the only line shown, not even the cover line: [0039](0039-incomplete-and-what-is-missing.md))
- **Date**: 2026-11-08

## Context

The UI must show what an album still needs. The discogs pipeline records its results as tags in the files, and external taggers change tags too. A separate database would drift from the files.

## Decision

### The files are the single source of truth

No state is stored besides settings ([0009](0009-settings-and-api-keys.md)). Everything shown is derived from the FLAC tags and stream info by `summarize(album)`.

### Album folders

An album is a folder that contains FLAC files. Folders named `Disc N` or `CD N` (any case, optional space) are grouped into their parent so a multi-disc album is one album. This is the same rule as `DISC_DIR_RE` in the discogs `disc_layout.py` (widened from `Disc N` only so the pipeline agrees): `ALBUM_DR` is always the mean over all discs, otherwise the discs would get different `VERSION` strings and album folder names. The two patterns must stay identical. `ROOT` itself is never an album.

### Six steps (in pipeline order)

| Step | Done when |
|------|-----------|
| Dynamic range | every track has `DYNAMIC_RANGE` |
| ReplayGain | every track has `REPLAYGAIN_ALBUM_GAIN` |
| Fingerprints | every track has `ACOUSTID_FINGERPRINT` |
| Tags and cover | a `DISCOGS_RELEASE_ID` exists and every track has `ARTIST`, `ALBUMARTIST`, `TITLE`, `ALBUM`, `TRACKNUMBER`, `DISCNUMBER`, `ALBUM_FORMAT`, `CATALOGNUMBER` (any of its four spellings; Discogs' own value `none` counts) and `DATE` or `YEAR`, and `VERSION` (the version string fixtags derives from year, DR, format, edition and catalogue number) |
| Lyrics | no track is missing lyrics (see below) |
| Filenames | every file name equals the bliss name of its tags ([0010](0010-bliss-file-naming.md)) |

Editing `ALBUM_EDITION`, `ALBUM_FORMAT` or `CATALOGNUMBER` in the tag editor ([0014](0014-internal-tag-editor.md)) to a different value removes `VERSION` from every file of an album that has a Discogs ID, so the Tags and cover step reopens and the album is Ready until the next Run fixes rewrites `VERSION` (and the folder name derived from it).

A step may be **done but partial** (shown yellow, still counts as done):
- Lyrics: at least one track has plain-text (not synced) lyrics.
- Tags and cover: the cover is smaller than the minimum cover size or missing ([0016](0016-cover-art.md)); the issue line has level `ingest`: the album keeps its status (Run fixes works, the pipeline needs no large cover) but cannot be moved to ingest.

Lyrics kinds per track, checked in this order (the same rule as the discogs `lrc_count.py`, which this mirrors):
1. Empty `LYRICS`: `instr` if `LYRICS_LANGUAGE` is `zxx`, else `none`.
2. `instr` (shown as **Instrumental**): the text contains the canonical sentinel `[instrumental:true]`, or a hand-typed marker `[MM:SS.xx][Instrumental]` / `[MM:SS.xx](Instrumental)` (case-insensitive, optional whitespace between the parts; `update_lyrics.py` rewrites these into the canonical block on its next run).
3. `lrc` (synced): contains a strict timestamp `[MM:SS.xx]` (two digits each).
4. `txt`: any other non-empty text.

A track is "missing" only when it is `none`. Any non-empty lyrics, synced, plain or instrumental, satisfy the step. The instrumental block itself contains `[00:00.00]`, which is why `instr` is tested before `lrc`.

### Album status

- `needs` (shown as **Needs input**): at least one blocking (`error` or `warn`) issue, see "Issue lines": no `DISCOGS_RELEASE_ID` (fixtags cannot run without it), an empty required tag, or files that disagree on an album-level tag. The server refuses to run such an album (409).
- `fixed`: no blocking issue and all six steps done.
- `ready`: everything else.

**Why the editor checks what the pipeline cannot:** the discogs scripts assume an external tag editor has filled the tags and silently substitute defaults (for example `fixtags.py` assumes the format `CD`, and `bliss.py` falls back to `ARTIST` and to track `00`). Tagwright is a tag editor too, so it does not let an album proceed with an empty required tag, and `ALBUMARTIST` (the album name is built from it) is required and has no `ARTIST` fallback.

### Issue lines

`summarize` also returns `issues`: the clearly identifiable problems of the album, **one line each**, recomputed from the tags on every refresh (so a line disappears as soon as an edit fixes it). Each has a level (`error` and `warn` block the album, `info` is a notice; `error` is used only for the Discogs release ID lines, is shown red and always listed first) and an action (which button the UI offers):

| Issue | Level | Action |
|-------|-------|--------|
| no `DISCOGS_RELEASE_ID` on the first file | **error** (red, first) | Search (Discogs assignment) |
| no catalog number (all tracks: "Add a catalog number (enter 'none' if the release has none)."; some: "N of M tracks have no catalog number") | warn | Tag Editor, Album tab |
| no album artist (`ALBUMARTIST`) or album format (`ALBUM_FORMAT`), on all or some tracks | warn | Tag Editor, Album tab |
| the files **disagree** on an album-level tag that `fixtags.py` and `bliss.py` read from the **first file only**: Discogs release ID, album artist, catalog number, album format (different values), and edition, MusicBrainz ID and the two overrides (different values, or set on only some tracks) | warn | Search for the release ID, else Tag Editor, Album tab (one save writes every file) |
| tracks without disc number, track number, title or artist (one line per tag, with counts) | warn | Tag Editor, Tracks tab |
| the same disc/track number on more than one file | warn | Tag Editor, Tracks tab |
| cover smaller than the minimum cover size (setting, default 1400 px, either side), or none | ingest (blocks only the move to ingest) | Upload |

**Without a Discogs release ID the Discogs line is the only blocker shown** (plus the cover line): the Discogs assignment fills or sets artist, album artist, album format, catalog number, titles and numbers ([0013](0013-discogs-track-assignment.md)), so the lines about them would only distract from the first thing to do. They appear again as soon as the album has a release ID and the tag is still missing. The album stays `needs` meanwhile.

Adding a rule here means adding it to `album_issues()` and this table. A check that the pipeline enforces by itself and that Tagwright cannot fix in the editor (for example the Discogs-derived `ALBUM` or dates) is not an issue line.

### Displayed values

Album DR is `ALBUM_DR`, falling back to the rounded mean of the track `DYNAMIC_RANGE` values. Artist is `ALBUMARTIST`, else `ARTIST`. "New folder" shows the bliss library path `<album artist>/<album [version]>` for information only; Tagwright does not rename album folders ([0010](0010-bliss-file-naming.md)).

### Scan cache

Per album, `summarize` results are cached in memory keyed by the signature `(file name, mtime_ns, size)` of all its files; any change by Tagwright or an external tagger changes the signature and invalidates the entry. Albums are scanned with 8 worker threads. Every Tagwright write endpoint additionally drops the album's entry before it returns the new summary (`fresh_summary`), because a write that keeps the file size (it fits the FLAC padding) on a network volume with coarse or cached timestamps could otherwise match the old signature. The cache is cleared when the input folder changes.

## Consequences

- External edits are seen on the next list load or refresh (no filesystem watcher yet; automatic re-scan was proposed, not built).
- The status model must change together with `nzbfix.py` if the pipeline gains or loses a step.
