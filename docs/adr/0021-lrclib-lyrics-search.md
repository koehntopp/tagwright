# ADR 0021: Lyrics search on lrclib.net in the track editor

- **Status**: Accepted
- **Date**: 2026-11-09

## Context

UC-8 (edit a track's title and lyrics, [0015](0015-track-playback-and-track-edit.md)). The pipeline fetches lyrics by an exact lookup ([0004](0004-pipeline-engine-reuses-discogs-scripts.md)) and leaves a track without lyrics when that misses (wrong artist, different title spelling, compilation). The owner needs to look at what lrclib.net has and pick a result by hand.

## Decision

- The track edit dialog has **Title** and **Artist** fields, prefilled from the tags and editable so that a cover version can be searched under the original artist or title. They are **search inputs only**: Save writes only the lyrics, the fields never block saving and the tags are not changed (title and artist are edited in the tag editor, [0014](0014-internal-tag-editor.md)).
- A **Search lrclib.net** button (the site's favicon, committed as `static/lrclib.ico`, [0005](0005-technology-stack-and-conventions.md)) in the lyrics header searches with the **current** title and artist fields (saved or not) and lists up to 20 results in a scrollable box to the right of the lyrics field: duration (green when within 3 s of the file's length; results are sorted by that distance), artist - title, album, and buttons **LRC**, **TXT** and **Instrumental** for what the result offers.
- A button replaces the lyrics field (Instrumental inserts the marker of [0015](0015-track-playback-and-track-edit.md)). Nothing is stored until Save; Cancel keeps the old lyrics.
- `GET /api/lrclib/search?title=&artist=` is **read-only** (no 409 while a job runs, writes nothing, reads no file). It calls `https://lrclib.net/api/search?track_name=&artist_name=` with `urllib`, a 15 s timeout and the user agent `Tagwright/<version> (+repository URL)`; failures answer 502 with a plain message shown in the results box. It does not use the discogs `Lrclib-App-Id` (registered for that application) nor the stored lrclib key ([0009](0009-settings-and-api-keys.md)); the search is user-triggered, one request per click.
- `GET /api/track` also returns `artist`, `album` and `length`.

## Consequences

- A hand-picked synced result is stored as it came; `update_lyrics.py` normalises it on its next run.
- Searching sends the title and artist text to lrclib.net, as the pipeline already does.
