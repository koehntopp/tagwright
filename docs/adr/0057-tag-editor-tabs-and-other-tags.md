# ADR 0057: Tag editor tabs: Discogs and MusicBrainz apart, and an Other tab

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0014](0014-internal-tag-editor.md) ("one dialog with three tabs", the combined **Discogs / Musicbrainz** tab)

## Context

The tab bar was too wide for its dialog: the last tab ran under the close button and its label was clipped. The combined Discogs / MusicBrainz tab was the longest label. Tags that no tab showed (genre, mood, comment, ReplayGain, fingerprints, encoder, ...) could not be seen in the editor at all.

## Decision

- Five tabs: **Album**, **Tracks**, **Discogs**, **MusicBrainz**, **Other**. The bar keeps the segmented style of the Settings dialog and leaves room for the close button. Tab names are short.
- **Discogs** and **MusicBrainz** show what the combined tab showed, one section each ([0014](0014-internal-tag-editor.md)).
- **Other** lists every tag that no other tab shows, read-only: key, the first file's value (two lines at most, the full value as tooltip) and, when it matters, "N of M files" (not every file has it) and "differs" (the files disagree). Not listed: the tags of the Album and Tracks tabs, the Discogs and MusicBrainz tags, `BARCODE`, `ASIN` and `LYRICS` (edited per track). `ALBUMARTIST` is listed, because the Album tab shows it only as small print. `GET /api/tags` returns it as `other`.
- Free-form editing of these tags is still not offered ([0014](0014-internal-tag-editor.md)).
