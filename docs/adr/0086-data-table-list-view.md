# ADR 0086: A data table for the list view

- **Status**: Accepted
- **Date**: 2026-11-18
- **Supersedes**: [0085](0085-list-view.md) (the view switch and the first list view)

## Context

[0085](0085-list-view.md) added a single button that toggled the board between a card grid and a compact list of albums. On a full library the list's mini covers cost a lot of vertical space and the rows are hard to compare: there is no way to reorder by a column or to give a long title more room. The owner also asked for the switch to be two adjacent buttons with the active one pressed, rather than one button that shows the other view.

## Decision

- **Top bar**: a small segmented control of **two 36 px icon buttons** directly right of **Rescan** and left of the Staging / Library switch: a grid icon for **Card view** and a list icon for **List view**. The active button is pressed (white with a soft shadow, like the active filter pill of [0031](0031-top-bar-again.md)); the other is flat. Both have tooltips and `aria-pressed`. The choice is kept in the browser under `tagwright-view`, as the folder switch is kept under `tagwright-area` ([0038](0038-staging-and-library-views.md)); cards are the default. UC-18 in [0002](0002-purpose-scope-and-use-cases.md) still describes the feature.
- The list view is a semantic HTML `<table>` (`thead`/`tbody`, header cells and row cells). Its six columns are **Album artist**, **Release name**, **Media**, **Edition**, **Release year** and **Master year**, in that order. There is no cover column: the status is a small dot in the artist cell with the status colours and tooltips of [0030](0030-ui-layout-and-design-system-v2.md) (red Needs input, blue Incomplete, green Fixed). The summary fields added by 0085 are kept.
- Rows alternate white and very light slate, with a hover shade and a stronger shade for the selected row. Clicking or pressing Enter/Space on a row selects that album and opens the same inspector as a card; filters, search, the folder switch and all dialogs work unchanged.
- Column widths start from sensible defaults. A drag handle at the right edge of each header resizes that column down to a minimum; widths are kept in the browser under `tagwright-table-widths`, so they survive a reload. The table scrolls horizontally when the widths exceed the board.
- Every column is sortable: click the header to sort ascending, click again for descending, and an arrow marks the active column. Years compare as numbers, the other columns with `localeCompare`; empty values sort last. This table sort is separate from the top-bar filter's sort cycle ([0031](0031-top-bar-again.md)): clicking a filter clears the table sort, and card view continues to use the top-bar sort. The table sort is not persisted.
- No new endpoint, setting, filter, tag or status is added.

## Consequences

- The list is denser: no cover requests, less vertical space per row, and columns can be widened for the data the owner cares about.
- Sorting in list view is independent of the card sort; switching views can show a different order, which is the point of a table.
- The two view buttons take the space of two Rescan buttons in the top bar; the search shrinks first if the bar runs out of room. Narrow screens scroll the table sideways instead of squeezing the columns.
