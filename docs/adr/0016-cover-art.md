# ADR 0016: Cover art: display, size warning, replacement

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

UC-9. Library quality needs a cover of at least 1400x1400. Covers are embedded in each FLAC; some albums only have a folder image.

## Decision

- **Which image**: `GET /api/cover` serves the embedded front cover (type 3) of the first file, else its first picture, else the first of `cover.jpg`, `folder.jpg`, `cover.png`, `folder.png` in the album folder, else answers 204 (no 404s in the console). The UI appends `&v=<album mtime>` so a replaced cover is not served from the browser cache. With no art, cards show a neutral gradient with initials.
- **Size**: `summarize` reports `{w, h, bytes, embedded}` for that same image. Mutagen's stored width/height are used; if they are 0 the image is decoded with Pillow. The inspector shows `W×H` under the cover; hovering shows embedded or not, and the size in KB/MB.
- **Minimum size (blocks ingest)**: below the **minimum cover size** on either side, or no cover, the **Tags and cover** step is partial (yellow) with the tooltip "Cover is WxH, below the minimum ..." **and** the album has an issue line of level `ingest` (yellow, with an Upload button): its status is unchanged and Run fixes still works (the pipeline needs no large cover), but Move to ingest is disabled and the server refuses it with 409 ([0006](0006-status-model-and-pipeline-steps.md), [0011](0011-ingestion-move.md)). The minimum is a setting (**Minimum cover size (pixels)**, `min_cover` in `settings.json`, default 1400, 0 turns the check off), see [0009](0009-settings-and-api-keys.md). Changing it re-evaluates every album.
- **Replace**: the upload icon (first of the icon row under the cover; the row is upload, musichoarders, albumartexchange, delete; the pixel size is on its own line below) opens a file picker; the browser sends the image as the raw body of `PUT /api/cover?path=`. The server verifies it is an image (400 otherwise), keeps JPEG and PNG bytes as they are, converts any other format to JPEG quality 95, and in every FLAC replaces the front and untyped (type 0) pictures with the new front cover, keeping other picture types (for example back cover). Refused while a job runs.
- **Drop target**: the cover image in the inspector accepts a dropped image file (a ring shows the target) and sends it through the same `PUT /api/cover` as the pen. A non-image drop is refused with a toast.
- **Delete**: a red circle-x beside the size (last in the icon row, shown only when the cover is embedded; an in-app confirmation dialog first, no browser popup) calls `DELETE /api/cover?path=`, which removes the front and untyped pictures from every FLAC and keeps other picture types. Folder images are never touched. Refused (409) while a job runs. The album then has no cover, so the minimum-size rule applies ([0006](0006-status-model-and-pipeline-steps.md)).
- **Cover search links**: in the icon row, links open `covers.musichoarders.xyz` (query `?artist=&album=`, committed icon `static/musichoarders.svg`, white glyph on a dark badge) and `albumartexchange.com` (`/covers?q=artist album`, icon `static/albumartexchange.ico`, supplied by the owner because the site answers 403 to automated requests; the link format is unverified) for the current album. They are plain links; Tagwright sends nothing to those sites.
- **Fetch from Discogs when missing**: assigning an album to a release ([0013](0013-discogs-track-assignment.md)) downloads the release's primary image (with the same one-request-per-second pacing as API calls) and embeds it, but **only when the first file has no embedded picture**; an existing cover, however small, is never replaced that way. Discogs images are often small (about 500 px in the test), so such a cover typically shows the yellow size warning; upload a better one with the pen.
- Pillow is the image dependency.

## Consequences

- `fixtags.py` resizes covers on a later run to its `cover_max_size` (default 1500 px); an uploaded cover larger than that is reduced then.
- A folder image is embedded only by uploading a cover; the pipeline does not embed it.
