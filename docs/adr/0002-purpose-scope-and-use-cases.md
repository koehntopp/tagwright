# ADR 0002: Purpose, scope and use cases

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The owner keeps a FLAC library and uses the `discogs` repository (`nzbfix.py` and its scripts) to turn freshly downloaded albums (a completed-downloads folder) into clean, tagged, loudness-analysed albums with lyrics, then moves them to an ingestion folder read by a music server (Roon, via bliss-style file names). That pipeline is a set of command-line scripts. Tagwright is a UI around that flow.

## Decision

Tagwright is a single-user, self-hosted web app that lets one person work through a queue of downloaded albums: see what each album needs, fix it, correct what automation cannot, and hand it to the library.

### Use cases

| ID | Use case | Where documented |
|----|----------|------------------|
| UC-1 | Choose an input folder and an output (ingest) folder, and enter the Discogs and lrclib API keys. | [0009](0009-settings-and-api-keys.md) |
| UC-2 | See all album folders of the input folder with cover, artist, album, year, edition, Discogs and MusicBrainz IDs, album DR, lyrics counts and a pipeline progress bar; filter by status, sort, search. | [0006](0006-status-model-and-pipeline-steps.md), [0017](0017-ui-layout-and-design-system.md) |
| UC-3 | Run the fix pipeline for one album and follow a live log. | [0004](0004-pipeline-engine-reuses-discogs-scripts.md), [0008](0008-job-model.md) |
| UC-4 | See per pipeline step whether it is done, and which tracks are missing it. | [0006](0006-status-model-and-pipeline-steps.md) |
| UC-5 | Move a fully fixed album to the ingest folder. | [0011](0011-ingestion-move.md) |
| UC-6 | Give an album the right Discogs release: search Discogs, assign the album's files to the release's tracks (the album often holds only a subset), renumber, and fill the tags the pipeline expects a tagger to have imported (artist, album artist, album title, catalog number, cover) when they are missing. | [0013](0013-discogs-track-assignment.md) |
| UC-7 | Edit tags the pipeline never overwrites (album artist/title overrides, format, edition, catalog number, MusicBrainz ID, per-track title/artist/disc/track/disc subtitle) and see, read-only, what Discogs writes. | [0014](0014-internal-tag-editor.md) |
| UC-8 | Play a track; edit a track's lyrics, optionally searching lrclib.net under another title or artist. | [0015](0015-track-playback-and-track-edit.md), [0021](0021-lrclib-lyrics-search.md) |
| UC-9 | See the cover's pixel size, be warned when it is small, replace it by uploading or dropping an image, delete the embedded cover, open cover searches on external sites. | [0016](0016-cover-art.md) |
| UC-10 | Rename files to the bliss pattern automatically after fixes and after edits. | [0010](0010-bliss-file-naming.md) |

### Out of scope

- Multi-user access, authentication, per-user settings ([0007](0007-trust-boundary-and-secrets.md)).
- A native macOS app (rejected, [0003](0003-deployment-web-app-in-docker.md)).
- The `lrc_fix` flow and the discogs repo's own `webui.py`; Tagwright does not replace or call them.
- MusicBrainz release search and tracklist assignment (only Discogs; MusicBrainz ID is a user-set tag).
- Editing audio, or any tag not listed in [0014](0014-internal-tag-editor.md).

## Consequences

New features must map to a use case here or add one (with an ADR). Features outside the scope above need an ADR that changes this one.
