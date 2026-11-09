# ADR 0017: UI layout and design system

- **Status**: Accepted (the Layout and No-stats-bar bullets are superseded by [0022](0022-top-bar-instead-of-sidebar.md))
- **Date**: 2026-11-08

## Context

The first UI did not match the intended design. The target is specified in `ui-redesign/DESIGN.md` with screenshots and a static mockup under `ui-redesign/`; later requests refined it.

## Decision

`ui-redesign/DESIGN.md` is the base specification; where this ADR differs, this ADR wins.

- **Layout** (superseded by [0022](0022-top-bar-instead-of-sidebar.md): the sidebar became a top bar; original text kept for history): three full-height columns, no page scroll, each column scrolls itself. Sidebar 240 px (the app icon `static/icon.svg` and the name at the top; navigation with counts; pipeline status footer with the status dot, job line, a red outlined **Stop** button that appears only while a job runs, and the settings gear; dot: blue pulsing running, green idle/done, red failed, amber stopped). Main area: sticky header (title, sort select, search with a ⌘K hint, rescan, **Run all ready**) and an auto-fill card grid (minimum card width 250 px). Inspector 600 px.
- **No stats bar, no filter tabs, no watched-folder box**: they duplicated the sidebar navigation; filtering is the sidebar's job.
- **Cards**: cover with status badge, title, `artist · year`, edition, a single badge row (Discogs and MusicBrainz favicons as links, DR, LRC in green, TXT in yellow), and a progress bar of done steps out of six.
- **Colours carry meaning**: status Needs input red, Ready blue, Fixed green; steps green when done, **yellow when done but partial**, grey when open; lyrics LRC green, TXT yellow, Instrumental blue, No lyrics red (badge columns are 6 rem wide so the longest label fits); Run fixes is the indigo primary action; Tag Editor is neutral dark. Do not reuse a colour for a different meaning.
- **Pipeline** is horizontal (six clickable steps); clicking a step marks each track in the Tracks box with a check or cross for that step.
- **Inspector order**: cover (with size and pencil) and header (artist and title with pencils, edition and year, ID badges linking to Discogs and MusicBrainz, each followed by a pen (Discogs: the release dialog of [0013](0013-discogs-track-assignment.md); MusicBrainz: the tag editor's Album tab with the MusicBrainz ID field focused), album DR), Tag Editor / Run fixes / Move to ingest, **one alert line per issue** ([0006](0006-status-model-and-pipeline-steps.md) "Issue lines": yellow for blockers, blue for notices, each with its button), new folder, pipeline, Tracks, Log.
- **Dialogs** (daisyUI `modal`): remove-cover confirmation 24 rem (in-app, never a browser `confirm()` popup), settings 48 rem, tag editor 72 rem, Discogs assignment 64 rem, track edit 72 rem (lyrics field on the left, lrclib.net results in a scrollable 26 rem box on the right; both 60% of the window height, at least 18 rem), album edit 40 rem. Help text under fields wraps (`whitespace-normal`). Widths use arbitrary values ([0005](0005-technology-stack-and-conventions.md)).
- **Feedback**: toasts bottom right for about 2.5 s; errors appear in the dialog that caused them or as an error toast.
- **Theme**: custom daisyUI theme `fixer` (light, indigo primary), Inter font, 14 px base, inline Lucide-style SVG icons, local icon files in `static/`.
- Targets 1440 to 1500 px wide desktop; no console errors.

## Consequences

- A visual change that alters these rules needs an ADR update; a visual change inside them does not.
