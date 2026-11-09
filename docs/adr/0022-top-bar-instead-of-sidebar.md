# ADR 0022: Top bar instead of a sidebar

- **Status**: Accepted
- **Date**: 2026-11-09
- **Supersedes**: the **Layout** and **No stats bar, no filter tabs** bullets of [0017](0017-ui-layout-and-design-system.md) (the rest of 0017 stands)

## Context

The 240 px sidebar held a logo, navigation entries and the pipeline status. At 1440 px it took 17% of the width from the card grid for very little content. The owner asked to move the navigation boxes to the top.

## Decision

- **Layout**: a full-width **top bar** (56 px) above two full-height columns: the card grid (scrolls itself) and the inspector (600 px, scrolls itself). No page scroll. The top bar has the same two zones: the left zone is as wide as the card column, the right zone as wide as the inspector (600 px, with a left border).
- **Left zone** (above the album list, side padding 2 rem, the same as the card grid so both edges line up): the app icon and the name "Tagwright" (the name only from 1500 px up), the three navigation entries (**All albums**, **Needs input**, **Fixed**; text and count badge, no icons, the active one dark `btn-neutral`; there is no Ready filter, ready albums show in All albums with their blue badge), then the search (up to 20 rem wide, shrinking when space is short; the ⌘K hint shows from 1600 px up, the shortcut always works), right-aligned the sort select (**Newest**, Title, Artist, Status; 7 rem wide so the label never runs into the arrow), rescan and the settings gear in the last place. There is no "Run all ready" button (removed at the owner's request: albums are run one at a time with Run fixes). Control text is 14 px. At 1440 px the zone is 840 px wide and everything fits.
- **Right zone** (above the inspector): the pipeline status (dot, "Pipeline" and the job line, the red outlined **Stop** button only while a job runs). The dot colours are unchanged ([0017](0017-ui-layout-and-design-system.md)).
- The navigation stays the only filter: no second navigation, stats bar or filter tabs are added.
- The "Library" page title and the icons in the navigation entries are dropped; the active navigation entry says where you are.
- Designed for 1440 px and wider; there is no narrow-screen layout.

## Consequences

- The grid gets the full width left of the inspector. The search field is small at 1440 px (a few dozen pixels of typing room) and grows on wider windows; if that is too tight, the sort select or the inspector width are the things to change.
