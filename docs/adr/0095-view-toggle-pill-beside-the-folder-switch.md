# ADR 0095: The view toggle is a pill; Rescan and the toggle sit beside the folder switch

- **Status**: Accepted
- **Date**: 2026-11-22
- **Supersedes**: the positions of Rescan in [0031](0031-top-bar-again.md) (directly after the filters) and of the view toggle in [0086](0086-data-table-list-view.md) (directly right of Rescan, flat), and the look of the toggle in 0086

## Context

The owner asked for the card/list buttons to sit inside a pill, and for Rescan and that pill to move between the filters and the search, next to the Staging / Library switch.

## Decision

- The filters stay at the left. **Rescan**, the **view toggle**, the **Staging / Library switch** and the **search** follow as one group on the right of the top bar's left zone, in that order, then the Settings gear.
- The view toggle is a **pill** like the folder switch: 36 px high, white, slate-300 border, fully rounded, holding the grid (Card view) and list (List view) icon buttons. The active one is shaded slate-200 with slate-900 icon, the other slate-400 (slate-700 on hover). Tooltips, `aria-pressed` and the stored choice (`tagwright-view`) are unchanged.

## Consequences

- The controls that change what the board shows (view, folder, search) sit together; the filters keep the left edge.
