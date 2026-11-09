# ADR 0022: Top bar instead of a sidebar

- **Status**: Accepted
- **Date**: 2026-11-09
- **Supersedes**: the **Layout** and **No stats bar, no filter tabs** bullets of [0017](0017-ui-layout-and-design-system.md) (the rest of 0017 stands)

## Context

The 240 px sidebar held a logo, four navigation entries and the pipeline status. At 1440 px it took 17% of the width from the card grid for very little content. The owner asked to move the navigation boxes to the top.

## Decision

- **Layout**: a full-width **top bar** (56 px) above two full-height columns: the card grid (scrolls itself) and the inspector (600 px, scrolls itself). No page scroll. The top bar has the same two zones: the left zone is as wide as the card column, the right zone as wide as the inspector (600 px, with a left border).
- **Left zone** (above the album list, left to right): the four navigation entries (**All albums**, **Needs input**, **Ready**, **Fixed**, text and count badge, no icons, the active one dark `btn-neutral`), then right-aligned the sort select, the search (the flexible element, 6 rem minimum; the ⌘K hint shows from 1600 px up, the shortcut always works), rescan and **Run all ready**. At 1440 px the zone is 840 px wide and these are tight; adding a control needs something else to give.
- **Right zone** (above the inspector): the pipeline status (dot, "Pipeline" and the job line, the red outlined **Stop** button only while a job runs) and the settings gear on the right. The dot colours are unchanged ([0017](0017-ui-layout-and-design-system.md)).
- The navigation stays the only filter: no second navigation, stats bar or filter tabs are added.
- The "Library" page title, the app name and the app icon in the page are dropped (the icon stays as the browser favicon, `static/icon.svg`, and the tab says Tagwright); the icons in the navigation entries are dropped too; the active navigation entry says where you are.
- Designed for 1440 px and wider; there is no narrow-screen layout.

## Consequences

- The grid gets the full width left of the inspector. The search field is small at 1440 px (about 53 px of typing room) and grows on wider windows; if that is too tight, the sort select or the inspector width are the things to change.
