# ADR 0088: The table title row stays at its inset

- **Status**: Accepted
- **Date**: 2026-11-18
- **Supersedes**: the sticky-header position of [0087](0087-table-contrast.md) (header stopped at the top bar) and the spacer-only alignment it added

## Context

ADR 0087 made the list table start 1.5 rem below the top bar, level with the inspector's details box, and made the title row stick at the very top of the board when scrolling. That means the title row first moves 24 px upward before it stops, and the owner reported that it still moves while scrolling. The owner chose to keep the aligned position and have the title row never move.

## Decision

- The table keeps its 24 px top inset. The title row sticks at **24 px** inside the board's scroll area, so its first painted position is its final position: it never shifts while scrolling.
- A sticky, opaque strip the colour of the board fills the 24 px above the title row while scrolling, so rows pass behind it instead of appearing above the header.
- Sticky positioning is applied to each `<th>` and the table uses separated borders with zero spacing. Collapsed table borders break sticky cells in some browsers.
- Card view, row shades, columns, sorting, resizing and selection are unchanged ([0087](0087-table-contrast.md)).

## Consequences

- The column names stay exactly level with the inspector's details box, including while the list scrolls.
- The 24 px strip is blank board colour between the top bar and the title row once scrolling starts.
