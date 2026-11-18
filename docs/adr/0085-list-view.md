# ADR 0085: A list view on the board

- **Status**: Accepted
- **Date**: 2026-11-18
- **Supersedes**: the **Top bar, left zone** bullet of [0031](0031-top-bar-again.md) (one round view-switch button is added) and the card-grid-only board of [0030](0030-ui-layout-and-design-system-v2.md) (a second, tabular layout)

## Context

The board is an auto-fill card grid ([0030](0030-ui-layout-and-design-system-v2.md), [0031](0031-top-bar-again.md)). With a large library the owner also wants a compact overview: one line per album with the mini album icon, album artist, release name, media, edition, release year and master year, so versions of the same release can be compared without opening each card. This needs a use case ([0002](0002-purpose-scope-and-use-cases.md)), a control in the top bar, and a second board layout. The navigation stays the only filter; the view switch is not a filter.

## Decision

- A use case **UC-18** is added to [0002](0002-purpose-scope-and-use-cases.md): switch the board between cards and a compact list of album details.
- **Top bar**: a round icon button directly right of **Rescan** and left of the Staging / Library switch toggles between card view (grid icon) and list view (list icon). Its tooltip names the view it switches to. The button is 36 px, like Rescan, so the 1440 px layout still fits; the search shrinks first if space runs out. The choice is kept in the browser under `tagwright-view`, as the folder switch is kept under `tagwright-area` ([0038](0038-staging-and-library-views.md)); card view is the default.
- **List view** replaces the card grid in the board area only. One row per album, with fixed-width columns in this order: mini cover (the same cover or initials fallback as a card), album artist, release name (`ALBUM`, falling back to the folder name as on a card), media (`ALBUM_FORMAT`), edition (`ALBUM_EDITION`), release year and master year. A header line names the columns; long values truncate. Clicking a row selects that album and opens the same inspector as clicking its card; the status dot keeps the status colours of [0030](0030-ui-layout-and-design-system-v2.md) and no new colour meaning is introduced. Filters, search, sort, the folder switch and every dialog work the same in both views.
- **Card view is unchanged**; the list is an extra way to look at the same albums. No filter tab, stats bar, new setting dialog or new endpoint is added.
- `summarize()` additionally returns `release_year` (`ALBUM_RELEASE_YEAR`, else `RELEASEDATE`/`DATE`), `master_year` (`ALBUM_MASTER_YEAR`, else `ORIGINAL YEAR`) and `edition_name` (`ALBUM_EDITION`), all truncated to their tag value. `SUMMARY_VERSION` is bumped so stored summaries are read again after the update ([0067](0067-stored-album-summaries.md)). The tags are read for display only; no pipeline step uses them as input ([0004](0004-pipeline-engine-reuses-discogs-scripts.md), [0014](0014-internal-tag-editor.md)).

## Consequences

- A change of view is local to the browser and survives a reload; it does not change what the server returns.
- The library's stored summaries are re-read once after the update, which takes a few minutes on the NAS share; after that the list view needs no extra tag reads.
- The list has the same selection and status model as the cards: it adds no way to change an album and no new filter.
