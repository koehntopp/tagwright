# ADR 0022: Top bar instead of a sidebar

- **Status**: Accepted
- **Date**: 2026-11-09
- **Supersedes**: the **Layout** and **No stats bar, no filter tabs** bullets of [0017](0017-ui-layout-and-design-system.md) (the rest of 0017 stands)

## Context

The 240 px sidebar held a logo, four navigation entries and the pipeline status. At 1440 px it took 17% of the width from the card grid for very little content. The owner asked to move the navigation boxes to the top.

## Decision

- **Layout**: a full-width **top bar** (56 px) above two full-height columns: the card grid (scrolls itself) and the inspector (600 px, scrolls itself). No page scroll.
- **Top bar, left to right**: app icon and name; the four navigation entries (**All albums**, **Needs input**, **Ready**, **Fixed**, each with its count badge, the active one dark `btn-neutral`); then right-aligned the sort select, the search with the ⌘K hint, rescan, **Run all ready**, and the pipeline status (dot, "Pipeline" and the job line, the red outlined **Stop** button only while a job runs, the settings gear). The dot colours are unchanged ([0017](0017-ui-layout-and-design-system.md)).
- The navigation stays the only filter: no second navigation, stats bar or filter tabs are added.
- The "Library" page title is dropped; the active navigation entry says where you are.
- Designed for 1440 px and wider; there is no narrow-screen layout.

## Consequences

- The grid gets the full width left of the inspector. The top bar is full at 1440 px; adding another control to it needs something else to shrink (the search field is the flexible one).
