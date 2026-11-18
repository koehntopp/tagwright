# ADR 0087: Higher-contrast, full-bleed table with DR

- **Status**: Accepted (the sticky-header position is superseded by [0088](0088-header-stays-at-inset.md))
- **Date**: 2026-11-18
- **Supersedes**: the row-shade part of the **List view** bullet of [0086](0086-data-table-list-view.md) (white / slate-50 rows, light dividers, padded board), the board padding of [0031](0031-top-bar-again.md), and the single "DR green" meaning of [0030](0030-ui-layout-and-design-system-v2.md) for this column

## Context

The list table of [0086](0086-data-table-list-view.md) alternated white and slate-50 rows with slate-200 lines, inside the board's 2 rem padding. The owner supplied references for a denser spreadsheet look: darker grey rows, near-black text, thin vertical cell dividers, a dynamic-range column with green and amber values, and a table that fills the board without whitespace around it. The top should line up with the inspector's details box, and the title row should stay visible while scrolling.

## Decision

- **Colours**: rows alternate **slate-200** and **slate-50**, with `slate-900` text in every cell. Thin **slate-300** vertical dividers separate cells and a slate-300 line separates rows. The header is slate-300 with slate-900 text and a slightly stronger divider. Hover darkens a row; the selected row uses a stronger slate-300 shade. The status dot keeps a white ring so it stays legible on the darker row. No status colour meaning changes.
- **Columns**: the full list is Album artist, Release name, Media, Edition, **Catalog #**, **DR**, **Release** and **Master**. The two year columns are labelled "Release" and "Master" and are narrow, with the full meaning in each header's tooltip. All columns sort, and their widths stay resizable.
- **Dynamic range**: the **DR** column shows the album's `dr` as two digits, right-aligned, and sorts numerically. Values **12 and above are green**, values **below 12 are amber**; an empty value is shown as empty. This is the only place a DR value is coloured by size; the pipeline-step green and the amber "partial" meaning of 0030 are unchanged elsewhere.
- **Layout**: the board has no horizontal or bottom padding; the table fills it edge to edge. Its top inset is 1.5 rem, the same as the inspector's details box ([0031](0031-top-bar-again.md)), so both start at the same height. The board scrolls in both directions; the table scrolls sideways when its columns are wider than the board.
- The header row is sticky at the top of the board's scroll area with an opaque slate-300 background, so the column names stay visible while scrolling.
- Sorting, resizing, the two-button view switch, selection and every other data field are unchanged ([0086](0086-data-table-list-view.md)).

## Consequences

- Rows are easier to track across the table and the column headings remain visible in a long library.
- The selected row and hover shade moved a step darker to stay distinct from the new alternating rows.
- The DR column gives a quick quality signal without opening the album; its green/amber threshold is a display rule only, not a status or a change to what makes a step done ([0054](0054-album-status-and-steps-consolidated.md)).
- Card view keeps its padding and its DR badge; only the list table is full-bleed.
