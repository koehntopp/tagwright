# ADR 0081: Disc subtitles are dividers in the track lists

- **Status**: Accepted
- **Date**: 2026-11-15
- **Supersedes in part**: [0014](0014-internal-tag-editor.md) (the Tracks tab's per-row "Disc subtitle" column and the "Disc subtitle" entry of the bulk edit), and, when the import dialogs are converted (second stage, below), the disc-scoped disc subtitle of [0078](0078-musicbrainz-track-assignment-and-import-song-titles.md)

## Context

A disc subtitle (`SET SUBTITLE` and `DISCSUBTITLE`, written as the same value) is a heading for a run of tracks. Discogs headings and MusicBrainz medium titles are such runs, and a disc can hold several (Main set, Encore); one subtitle can also span only part of a disc. A text column repeated in every row hides that, and a line of small print under the import checkbox lost it entirely. The owner asked for the subtitles to divide the track list, the same way in the Tag Editor and in the Discogs and MusicBrainz dialogs, with a pen to assign a "proper" subtitle.

## Decision

One shared component, `SubtitleDivider` (`ui/components/subtitle-divider.tsx`), draws a divider band in every track list; its look and behaviour are the same everywhere and are changed in one place.

- **Where a divider is drawn.** A *run* is a series of neighbouring tracks with the same disc and the same subtitle. A divider starts every run that begins a disc or a new subtitle. On an album with several discs every disc has one (a dark **Disc N** chip, the subtitle, the number of files, a pen); on a single-disc album only a run with a subtitle has one, without the chip. A subtitle change inside a disc gets a lighter, indented divider without the chip and with an **x**. A disc without a subtitle shows the grey italic text "No subtitle".
- **Pen.** Turns the divider's text into an input with **Set** and **Cancel**. Set writes the text as the subtitle of every track of the run (an empty text clears it).
- **x** (on dividers inside a disc): the run takes the subtitle of the run above, so the two merge.
- **"+ divider here"**: between two tracks, visible while the pointer is near the gap or the gap has the keyboard focus (hover target about 12 px, reachable with Tab, Enter activates); not offered where a divider already is. It opens an empty input; Set gives the tracks from there to the end of the run that subtitle, Cancel or an empty text changes nothing.
- **Reordering** (Tag Editor): disc, track number and subtitle belong to the **positions**, like the numbers in [0014](0014-internal-tag-editor.md): a track dragged across a divider takes that run's subtitle.
- **Colours** ([0030](0030-ui-layout-and-design-system-v2.md)): a divider that shows data of the files (Tag Editor) is light blue with a dark blue chip; in the import dialogs release data is blue and the file's own data grey ([0078](0078-musicbrainz-track-assignment-and-import-song-titles.md)).

**Stages.** (1) The component and the Tag Editor's Tracks tab (the "Disc subtitle" column and its bulk-edit entry go). (2) The Discogs and MusicBrainz dialogs: dividers where the release's subtitle changes (every Discogs heading, every MusicBrainz medium title), with a Release / Keep mine choice per divider (default Keep mine when the files already carry a different non-empty subtitle), "Was:" listing the files' current subtitles, and the apply endpoints taking a subtitle per run instead of per disc. Stage 2 gets its own text here when it is built.

## Consequences

- No new endpoint and no change to what is stored: the subtitle is still the per-track `SET SUBTITLE` / `DISCSUBTITLE` of the existing save ([0014](0014-internal-tag-editor.md)).
- The Tag Editor and the import dialogs must stay consistent: a change to the divider is a change to the shared component.
