# ADR 0081: Disc subtitles are dividers in the track lists

- **Status**: Accepted (the order of the rows in the import dialogs is set by [0089](0089-assignment-track-order.md); the disc a divider names: [0102](0102-one-release-track-on-several-discs.md); how an import-dialog divider reads: [0106](0106-clearer-subtitle-dividers-and-current-release-id.md))
- **Date**: 2026-11-15
- **Supersedes in part**: [0014](0014-internal-tag-editor.md) (the Tracks tab's per-row "Disc subtitle" column and the "Disc subtitle" entry of the bulk edit), and the disc-scoped disc subtitle of [0078](0078-musicbrainz-track-assignment-and-import-song-titles.md)

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

**The import dialogs (Discogs and MusicBrainz; built).** They draw the same dividers over the file -> release track table, using the release's subtitle of each *assigned* release track:

- Release data per track: `subtitle` on every release track. **Discogs**: every heading starts a run with that title (a leading `CD n` / `Disc n` label stripped; a heading that is only that label gives none), the run lasts until the next heading or the next disc, and a new disc without a heading has none. **MusicBrainz**: the medium's title. A divider is drawn where the disc or the release's subtitle changes between neighbouring assigned files (skipped files stay with the run above).
- Each divider shows the release's subtitle (blue, editable with the pen), "Was:" with the distinct subtitles the files carry now, a yellow "differs from your subtitles" chip when they differ, and a **Release / Keep mine** toggle. **Keep mine** writes nothing for the files of that run. The default is Keep mine when a file of the run already has a non-empty subtitle that differs from the release's, otherwise Release. Typing a subtitle switches the run to Release.
- "+ divider here" splits a run by hand, the x removes a divider (a hand-made one disappears; one of the release is merged into the run above). An empty subtitle is never written.
- The checkbox "Import song titles" sits in the release line at the top right of both dialogs; with it off the dividers are grey and inactive and nothing is written.
- `POST /api/tracks/apply` and `POST /api/musicbrainz/apply` take `subtitle` in each assignment: a text is written as `SET SUBTITLE` and `DISCSUBTITLE`, `null` (Keep mine) leaves the file alone, no key writes the release track's own subtitle. `POST /api/tracks/propose` returns each file's current `subtitle`. This replaces the `discs` list of the release answers.

## Consequences

- No new endpoint and no change to what is stored: the subtitle is still the per-track `SET SUBTITLE` / `DISCSUBTITLE` of the existing save ([0014](0014-internal-tag-editor.md)).
- The Tag Editor and the import dialogs must stay consistent: a change to the divider is a change to the shared component.
