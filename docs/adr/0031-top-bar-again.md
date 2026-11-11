# ADR 0031: Top bar again, no sidebar, no Artists list

- **Status**: Accepted (the right zone also holds the library status: [0037](0037-library-watcher-and-layout.md))
- **Date**: 2026-11-10
- **Supersedes**: the **Layout** bullet of [0030](0030-ui-layout-and-design-system-v2.md) (the 256 px sidebar and its Artists list and bottom status card); the rest of 0030 stands

## Context

With the new look ([0029](0029-nextjs-frontend-static-export.md), [0030](0030-ui-layout-and-design-system-v2.md)) the owner asked to move the logo, the filters and the rescan button into the top menu and drop the sidebar, as [0022](0022-top-bar-instead-of-sidebar.md) had done before. The sidebar's other items need a new place or go.

## Decision

- **Layout**: a full-width **top bar** (56 px, cool light grey `#e9edf3`, bottom border; the card board behind it is `#f1f4f9`, the inspector stays white) above two full-height columns: the card board (scrolls itself, padding 2 rem) and the inspector (600 px, left border, scrolls itself). No page scroll; 1440 px and wider.
- **Top bar, left zone**: the app icon (`/static/icon.svg`) alone, no name; the four filters **All albums**, **Needs input**, **Ready**, **Fixed** as pills in 17 px medium-weight text with a plain grey count (the active one a white pill with a soft shadow, as in the Anchor reference); **clicking the active filter again cycles the sort** Newest, Title, Artist, Status (a toast names it, the pill's tooltip shows it); there is no sort dropdown; a round **Rescan** icon button; the search (up to 18 rem, shrinks when space is short; the ⌘K hint from 1600 px up, the shortcut always works); right-aligned, in the place the sort select had, the **Settings** gear (20 px icon).
- **Top bar, right zone** (600 px, above the inspector): the pipeline status (dot, "Pipeline", job line, a red outlined **Stop** button only while a job runs; dot colours as in 0017).
- **Removed**: the sidebar, the page title row with the album count (the filter badges carry the counts), the **Artists** list (the search field finds an artist by name). The navigation stays the only filter; no stats bar or filter tabs.
- Cards, colours, inspector, dialogs, toasts and theme are unchanged ([0030](0030-ui-layout-and-design-system-v2.md)).

## Consequences

- The board gets the full width left of the inspector. The search is narrow at 1440 px and grows on wider windows.
- Rules of 0022 about widths of the old top bar do not apply; the zones above replace them.
