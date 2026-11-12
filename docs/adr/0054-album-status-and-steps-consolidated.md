# ADR 0054: Album status, pipeline steps and issue lines (consolidated)

- **Status**: Accepted (the scan cache is stored in SQLite and checked against the watcher's index: [0067](0067-stored-album-summaries.md))
- **Date**: 2026-11-12
- **Supersedes**: [0006](0006-status-model-and-pipeline-steps.md), [0039](0039-incomplete-and-what-is-missing.md), [0049](0049-tag-edits-refresh-the-version-at-once.md), [0050](0050-lyrics-are-optional.md). This is the one place that states the current rules; the four stay as history. The filter and colours of the board are in [0026](0026-ready-filter-returns.md) and [0030](0030-ui-layout-and-design-system-v2.md); the move gate is [0011](0011-ingestion-move.md).

## Context

The UI must show what an album still needs. The pipeline records its results as tags in the files, and external taggers change tags too. A separate database would drift from the files.

## Decision

### The files are the single source of truth

No state is stored besides settings ([0009](0009-settings-and-api-keys.md)). Everything shown is derived from the FLAC tags and stream info by `summarize(album)`.

### Album folders

An album is a folder that contains FLAC files. Its tracks are the files in its own folder and those in its `Disc N` / `CD N` subfolders (any case, optional space), so a multi-disc album is one album; other subfolders are other albums. This is the rule of `DISC_DIR_RE` in `pipeline/layout.py`: `ALBUM_DR` is always the mean over all discs, otherwise the discs would get different `VERSION` strings and folder names. The staging folder itself is never an album, and hidden folders and files (a name starting with a dot) are not read.

### Six steps (in pipeline order)

| Step | Done when |
|------|-----------|
| Dynamic range | every track has `DYNAMIC_RANGE` |
| ReplayGain | every track has `REPLAYGAIN_ALBUM_GAIN` |
| Fingerprints | every track has `ACOUSTID_FINGERPRINT` |
| Tags and cover | a `DISCOGS_RELEASE_ID` exists and every track has `ARTIST`, `ALBUMARTIST`, `TITLE`, `ALBUM`, `TRACKNUMBER`, `DISCNUMBER`, `ALBUM_FORMAT`, `CATALOGNUMBER` (any of its four spellings; Discogs' own value `none` counts) and `DATE` or `YEAR`, and `VERSION` (the version string fixtags derives from year, DR, format, edition and catalogue number) |
| Lyrics | no track is missing lyrics (see below); **optional**, see "Album status" |
| Filenames | every file name equals the file name of the layout for its tags ([0010](0010-bliss-file-naming.md), [0037](0037-library-watcher-and-layout.md)) |

**The bar** in the inspector shows each step as a 36 px circle with the step's icon (dynamic range: bar chart, ReplayGain: speaker, fingerprints: fingerprint, tags and cover: tags, lyrics: microphone, filenames: file), joined by a thin line in pipeline order. State: a green circle with a check badge is done, an amber one with a warning badge is done but partial, a white one with a grey icon is open (dashed outline for the optional Lyrics step), a blue spinning one is running ([0051](0051-run-a-single-pipeline-step.md)).

**Editing the version inputs.** Saving the tag editor ([0014](0014-internal-tag-editor.md)) with a changed `ALBUM_EDITION`, `ALBUM_FORMAT` or `CATALOGNUMBER` on an album with a Discogs release ID removes `VERSION`, writes the other edits, then runs the Discogs tags step (`fix_album`, as an assignment does) so `VERSION` is rewritten before the response; the files are then renamed. The log says "Discogs tags refreshed: ... [version]". If the step cannot run (no key, Discogs down) the removed `VERSION` stays removed: Tags and cover reopens and the album is Incomplete until a run, and the log says "not refreshed". Saving without such a change does not call Discogs. The editor closes on Save and the inspector's step circles spin until the server answers (*Tags & cover* and *Filenames* after such an edit, *Filenames* alone otherwise; a failed save shows a toast).

A step may be **done but partial** (shown yellow, still counts as done):
- Lyrics: at least one track has plain-text (not synced) lyrics.
- Tags and cover: the cover is smaller than the minimum cover size or missing ([0016](0016-cover-art.md)); the issue line has level `ingest`: the album keeps its status (Run fixes works) but cannot be moved to the library.

Lyrics kinds per track, checked in this order (the same rule as the discogs `lrc_count.py`, which this mirrors):
1. Empty `LYRICS`: `instr` if `LYRICS_LANGUAGE` is `zxx`, else `none`.
2. `instr` (shown as **Instrumental**): the text contains the canonical sentinel `[instrumental:true]`, or a hand-typed marker `[MM:SS.xx][Instrumental]` / `[MM:SS.xx](Instrumental)` (case-insensitive, optional whitespace between the parts; `update_lyrics.py` rewrites these into the canonical block on its next run).
3. `lrc` (synced): contains a strict timestamp `[MM:SS.xx]` (two digits each).
4. `txt`: any other non-empty text.

A track is "missing" only when it is `none`. Any non-empty lyrics, synced, plain or instrumental, satisfy the step. The instrumental block itself contains `[00:00.00]`, which is why `instr` is tested before `lrc`.

### Album status

- `needs` (shown as **Needs input**, red): at least one blocking (`error` or `warn`) issue, see "Issue lines": no `DISCOGS_RELEASE_ID` (fixtags cannot run without it), an empty required tag, or files that disagree on an album-level tag. The server refuses to run such an album (409), except the single steps that only measure the audio (Dynamic range, ReplayGain, Fingerprints; [0051](0051-run-a-single-pipeline-step.md)).
- `fixed` (**Fixed**, green): no blocking issue and every step **except Lyrics** done. Lyrics are optional: some tracks have none anywhere (a medley, a spoken intro, a remix lrclib does not know), and one such track must not keep an album from moving.
- `ready` (shown as **Incomplete**, blue; the key stays `ready`): everything else. "Ready" read as "ready to move", which is what Fixed means.

**Why the editor checks what the pipeline cannot:** the discogs scripts assume an external tag editor has filled the tags and silently substitute defaults (for example `fixtags.py` assumes the format `CD`, and `bliss.py` falls back to `ARTIST` and to track `00`). Tagwright is a tag editor too, so it does not let an album proceed with an empty required tag, and `ALBUMARTIST` (the album name is built from it) is required and has no `ARTIST` fallback.

### What is missing

The summary has `missing`: for every open step the tracks that fail it, `{step, label, count, of, tracks, optional}` (up to 12 track names). Labels: **No lyrics**, **No DR**, **No ReplayGain**, **No fingerprints**, **Tags incomplete**, **Names differ**. Lyrics are `optional: true`.
- **Card**: for an Incomplete album the pill on the cover names the first *required* missing item (`No DR +1`) instead of the status word, never lyrics. Below the DR and lyrics badges, one pill per missing item with its track count (`No DR 2`, hover: the track names): red for required items, **blue for optional ones** (`No lyrics 2`).
- **Inspector**: a red **Missing** box above the pipeline lists each required item ("No DR on 2 of 4 tracks" and the first track names); a blue **Optional** box lists the optional ones. Clicking an entry marks those tracks in the track list, as clicking the step does.
- Run fixes keeps trying the lyrics step as before. Albums in the library that lack lyrics show as Fixed with the blue notice.
- No new filter and no search syntax ([0030](0030-ui-layout-and-design-system-v2.md): the top bar navigation is the only filter).

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

**Without a Discogs release ID the red Discogs line is the only line shown** (not even the cover line) and there is no `missing` list, so no badges and no Missing box: the Discogs assignment fills or sets artist, album artist, album format, catalog number, titles and numbers ([0053](0053-discogs-search-and-assignment-consolidated.md)), so the lines about them would only distract from the first thing to do. They appear again as soon as the album has a release ID and the tag is still missing. The album stays `needs` meanwhile.

Adding a rule here means adding it to `album_issues()` and this table. A check that the pipeline enforces by itself and that Tagwright cannot fix in the editor (for example the Discogs-derived `ALBUM` or dates) is not an issue line.

### Displayed values

A **missing** Discogs or MusicBrainz ID is shown as a link in the inspector and the tag editor: it opens that site's release search in a new tab for the artist and the album title as they are shown at that moment (overrides included).

Album DR is `ALBUM_DR`, falling back to the rounded mean of the track `DYNAMIC_RANGE` values. Artist is `ALBUMARTIST`, else `ARTIST`. The inspector's header line starts with the release country's flag (emoji, from `DISCOGS_ALBUM_RELEASECOUNTRY`, else `COUNTRY`, else the MusicBrainz country code; no flag for regions without one, the country name is the tooltip), then the `VERSION` string, which already holds year, DR, format and catalogue number. Before `VERSION` exists it shows the year, the media type (`ALBUM_FORMAT`, `CD` when unset, the format `fixtags` assumes) and the catalogue number. "New folder" shows the library path from the layout for information only; Tagwright does not rename album folders in staging ([0010](0010-bliss-file-naming.md)).

### Scan cache

Per album, `summarize` results are cached in memory keyed by the signature `(file name, mtime_ns, size)` of all its files; any change by Tagwright or an external tagger changes the signature and invalidates the entry. Albums are scanned with 8 worker threads. Every Tagwright write endpoint additionally drops the album's entry before it returns the new summary (`fresh_summary`), because a write that keeps the file size (it fits the FLAC padding) on a network volume with coarse or cached timestamps could otherwise match the old signature. The cache is cleared when the staging folder changes.

## Consequences

- External edits to the staging folder are seen on the next list load or refresh (it has no watcher). The library has its own watcher ([0037](0037-library-watcher-and-layout.md)).
- The status model must change together with the pipeline if it gains or loses a step.
- Saving a format, catalogue number or edition edit costs one Discogs request.
