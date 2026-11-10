# ADR 0030: UI layout and design system v2 (sidebar, shadcn/ui)

- **Status**: Accepted (the Layout bullet, the sidebar, is superseded by [0031](0031-top-bar-again.md); everything else stands)
- **Date**: 2026-11-10
- **Supersedes**: [0017](0017-ui-layout-and-design-system.md) (layout, dialogs mechanism, theme; the colour meanings, pipeline, copy icons, inspector order and widths are carried over below), [0022](0022-top-bar-instead-of-sidebar.md) (the top bar is replaced by a sidebar again) and the top-bar location of the Ready filter in [0026](0026-ready-filter-returns.md) (the filter itself stays)

## Context

The frontend moved to Next.js and shadcn/ui ([0029](0029-nextjs-frontend-static-export.md)) with a sidebar-and-cards look chosen by the owner. The behaviour of every screen stays as the earlier ADRs describe it; this ADR fixes the new layout and design rules. Use cases are unchanged (UC-2 to UC-11).

## Decision

- **Layout**: three full-height columns, no page scroll, each column scrolls itself, designed for 1440 px and wider.
  - **Sidebar** (256 px, light grey): the icon-style mark and the name "Tagwright" in a serif face; a dark **Rescan folder** button; navigation with counts (**All albums**, **Needs input**, **Ready**, **Fixed**; the active entry is a white pill); an **Artists** list (the 12 artists with most albums, with counts; clicking one puts the name in the search, clicking it again clears it; it is a shortcut to the search, not a second filter); at the bottom the **pipeline status card** (dot, "Pipeline", job line, a red outlined **Stop** button only while a job runs) and **Settings**.
  - **Main**: a header with the page title (the active filter's name and the number of shown albums), the search (placeholder "Search albums, artists, IDs", ⌘K focuses it) and the sort select (**Newest**, Title, Artist, Status); below it an auto-fill card grid (minimum card width 240 px).
  - **Inspector** (600 px, left border): as in 0017.
- **No stats bar and no filter tabs**: the sidebar navigation is the only filter. There is no "Run all" button.
- **Cards**: rounded, tinted by status (Needs input red, Ready blue, Fixed green); cover with a status pill, title, `artist · year`, edition, two badge rows (first the Discogs and MusicBrainz ID links with their icons, second DR, LRC green, TXT yellow), progress bar of done steps out of six. The selected card has a dark ring. The card of the album that is playing shows an animated yellow equalizer badge top right on the cover ([0015](0015-track-playback-and-track-edit.md)). Copy icons after title and artist ([0017](0017-ui-layout-and-design-system.md) rule kept: a click does not select the card).
- **Colours carry meaning** (unchanged): status red / blue / green; steps green when done, **yellow when done but partial**, grey when open; lyrics LRC green, TXT yellow, Instrumental blue, No lyrics red (fixed-width badge columns); DR green; issue alerts yellow (blocker), blue (notice) and red (the missing or disagreeing Discogs release ID, always first), plus blue MusicBrainz consistency notes under the issues ([0023](0023-musicbrainz-release-search.md)). The primary action buttons are the dark slate ones (Tag Editor, Save, Search, Rescan); Run fixes and Move to ingest are outlined. Do not reuse a colour for another meaning.
- **Pipeline** is a horizontal row of six numbered circles (a check mark when done); clicking one marks each track in the Tracks box with a check or cross for that step.
- **Inspector order**: as in 0017 (cover with upload / search links / remove and size; header with pencils, edition and year, ID badges with pens, album DR; Tag Editor / Run fixes / Move to ingest; one alert per issue; new folder; pipeline; Tracks; Log).
- **Dialogs** are shadcn `Dialog`s. The Tag editor can stay open while the Discogs, MusicBrainz or lyrics dialog is open above it. Widths: remove-cover and move confirmations 24 rem (in-app, never a browser `confirm()`), settings 48 rem, tag editor 72 rem, Discogs assignment 64 rem, MusicBrainz release 64 rem, track edit 72 rem (lyrics field left, lrclib.net results in a scrollable 26 rem box right, both 60% of the window height, at least 18 rem), album edit 40 rem. Help text under fields wraps. Move to ingest asks for confirmation in a dialog.
- **Feedback**: sonner toasts bottom right; errors appear in the dialog that caused them or as an error toast.
- **Theme**: Tailwind slate neutrals, white cards on a `slate-50` page, rounded-2xl cards, Geist sans, serif wordmark, 14 px base, lucide icons, local icon files in `static/`.
- No console errors at 1440 px.

## Consequences

- A visual change inside these rules needs no ADR; one that changes them does.
- The old rules about the top bar (width zones, hidden ⌘K hint, 7 rem sort select) no longer apply.
