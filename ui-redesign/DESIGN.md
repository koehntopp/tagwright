# Album Fixer: UI redesign spec (daisyUI)

This is the target design for the Album Fixer web UI. It replaces the current layout: a single list on the left and one long detail page.

- The screenshots of the original mock were removed; this design is superseded by [ADR 0030](../docs/adr/0030-ui-layout-and-design-system-v2.md).
- `reference/daisy.html` is a working static mockup with fake data (`reference/data.js`). Treat it as the source of truth for markup, classes and spacing. You can copy from it freely.
- `reference/daisy.in.css` is the Tailwind v4 + daisyUI 5 entry file, including the custom theme.

Keep all existing backend behaviour. This is a front-end restructure: same data, same actions, new layout.

---

## 1. Stack

- **Tailwind CSS v4 + daisyUI v5.** daisyUI is a Tailwind plugin that adds component classes (`btn`, `card`, `badge`, `menu`, `stats`, `steps`, `tabs`, `collapse`, `mockup-code`, `toast`, `alert`).
- Use whatever build the project already has. If it has none, either:
  - use the Tailwind standalone CLI with `daisy.in.css` as input (no Node project needed), or
  - for quick iteration, use the CDN build: `<link href="https://cdn.jsdelivr.net/npm/daisyui@5" rel="stylesheet">` + `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>`. In that case the custom theme has to be set in a `<style type="text/tailwindcss">` block.
- Font: **Inter** at 400, 500, 600 and 700. Base size is 14px.
- Theme: the custom daisyUI theme `fixer` in `daisy.in.css`. It's light, with an indigo primary (`oklch(55% .2 275)`), radius-box `.75rem`, radius-field `.5rem`, depth 0 and noise 0. Copy it verbatim.
- Icons: inline Lucide-style SVGs (24×24 viewBox, stroke 2, round caps). Any Lucide icon set is fine.

## 2. Layout

There are three full-height columns and no page scroll. Each column scrolls on its own.

```
┌──────────┬───────────────────────────────────┬──────────────┐
│ Sidebar  │ Header (sticky): title · search · │  Inspector   │
│ 240px    │   primary action                  │  400px       │
│          ├───────────────────────────────────┤  (selected   │
│ nav      │ Stats bar (4 stats)               │   album)     │
│ + counts │ Filter tabs ........ sort label   │              │
│          │ Album card grid                   │              │
│ watched  │  (auto-fill, min 190px)           │              │
│ folder   │                                   │              │
│ ──────── │                                   │              │
│ footer   │                                   │              │
└──────────┴───────────────────────────────────┴──────────────┘
```

- Wrapper: `flex h-screen overflow-hidden`, with `bg-base-200` on the body.
- Sidebar and inspector use `bg-base-100` and a `border-base-300` border. The main area uses `bg-base-200`.

## 3. Mapping from the current UI

| Current UI | New location |
|---|---|
| Folder path input + **Change folder** + **Rescan** (top bar) | Sidebar → "Watched folder" box: path in mono, with **Change** and **Rescan** as `btn-xs btn-ghost` |
| Left album list | Main → **card grid** |
| Badges `D 4555850`, `MB bbdc3aba…` | Inspector header: `badge badge-ghost badge-sm font-mono` |
| `D missing` / `MB missing` | Inspector header: `badge badge-error badge-soft badge-sm` |
| Status `Ready` / `Fixed` / `No ids` | Card overlay badge: `badge-info` "Ready", `badge-success` "Fixed", `badge-error` "Needs IDs" (rename "No ids" to **Needs IDs**) |
| Detail title + cover | Inspector header: 96px cover, small artist line, title `text-xl font-semibold`, edition line |
| Album artist / Album / Tracks / DR / Lyrics / New title table | Inspector key-value rows (label left in `text-base-content/50`, value right). DR as `badge badge-success badge-soft`. New title in a full-width `code` block below |
| Lyrics progress bar + "8 synced, 0 plain…" | Inspector row "Lyrics": `8 synced · 0 plain` |
| Pipeline checklist | Inspector → `ul.steps.steps-vertical`. Completed steps get `step-success` + `data-content="✓"`, and pending steps show their number. Use `[&_.step]:min-h-11` to keep it compact |
| **Run fixes** / **Move to ingest** | Inspector, side by side under the header: `btn btn-primary btn-sm flex-1` and `btn btn-sm flex-1` |
| Log panel | Inspector bottom: `collapse collapse-arrow bg-base-200` holding a `mockup-code` block. Open it automatically while a run is in progress or has finished |

## 4. Components in detail

### Sidebar
- Brand row (h-16): 32px rounded `bg-primary` square with a music-note icon, then "Album Fixer" in semibold.
- `ul.menu`: **All albums · Needs IDs · Ready · Fixed**, each with an icon and a count badge at the right. The active item uses `menu-active`, and its badge is solid; the other badges use `badge-ghost`. These items set the same filter as the tabs in the main area and stay in sync with them.
- An optional "Ingested" item with a count, if the backend can provide one.
- The "Watched folder" section is described in §3.
- Footer, pinned with `mt-auto`, border-top: a status line such as "Roon ingest · idle". This is optional; remove it if there's no data for it.

### Main header (sticky, `backdrop-blur`, `bg-base-200/80`)
- Title on the left: "Library".
- On the right:
  - search `label.input.input-sm` (w-72) with a search icon and a `kbd` "⌘K" hint. It filters by title, artist or ID on the client side.
  - **Run all ready** as `btn btn-sm btn-primary` with a play icon. It runs fixes for every album whose status is Ready.

### Stats bar
`div.stats` holding 4 `stat` blocks: **In folder** (album count), **Needs IDs** (`text-error`), **Ready to fix** (`text-info`), **Fixed** (`text-success`, desc "Waiting for ingest"). The values are `text-2xl`. The track count and GB under "In folder" are optional.

### Filter row
`tabs tabs-box tabs-sm` with All / Needs IDs / Ready / Fixed, plus a muted "Sorted by recently added" label at the right.

### Album card (`card`)
- The whole card can be clicked and selects the album for the inspector.
- Selected card: `border-primary ring-2 ring-primary/20`. Other cards: `border-base-300`, `shadow-sm`, and `hover:shadow-md`.
- Square cover (`aspect-square`) with the status badge overlaid top-left.
- Body (`p-4`): title (semibold, truncate), "Artist · Year" (`text-base-content/60`), edition (`text-base-content/40 text-xs`).
- Footer row: a thin `progress` (h-1.5) showing completed pipeline steps out of 6, plus an "n/6" label. It's `progress-success` at 6/6 and `progress-primary` otherwise.
- Use the real embedded cover art. The coloured gradients in the mockup are only placeholders. If an album has no art, use a neutral gradient with the artist initials.

### Inspector
- Covered in §3. Extra behaviour:
  - **Needs IDs** state: show `alert alert-warning alert-soft` reading "Add a Discogs or MusicBrainz release ID before running fixes." with a "Search" `btn-xs`, and disable **Run fixes**.
  - Enable **Move to ingest** only when the status is Fixed.
- Section headings ("Pipeline") are `text-xs uppercase tracking-wider text-base-content/50`.

### Log
- `mockup-code` with one `<pre data-prefix="HH:MM:SS">` per line. The current UI shows raw JSON log events; parse them and show only `timestamp` + `event`.
- Colours: success or "done" lines get `text-success`, file renames get `opacity-60`, everything else uses the default colour.
- Auto-scroll to the bottom while a run is in progress. Stream lines in the same way the current log does.

### Toasts
`div.toast.toast-end` in the bottom-right corner, holding an `alert alert-success` for about 2.5 seconds. Show one after Rescan, Run fixes (started and finished), and Move to ingest.

## 5. States & behaviour

- **Status model:** `needs` (no Discogs or MB ID) → `ready` (IDs present, pipeline not run) → `fixed` (pipeline finished) → moved to ingest, at which point the album disappears from the folder.
- **While running:** the card progress bar and the inspector steps update as each stage finishes, the current step shows a spinner (`loading loading-spinner loading-xs`), and the log streams.
- **Selection** stays the same when filters change. If the selected album is filtered out, keep showing it in the inspector anyway.
- **Empty state** (no albums, or the filter matches nothing): a centred muted message in the grid area.

## 6. Mockup items that need backend data. Skip any that don't exist
- Track count and folder size in the stats bar
- "Ingested" count in the sidebar
- Ingest status in the sidebar footer
- Edition line (e.g. "SACD · 2003"): derive it from the folder name or tags if that's easy
- "Sorted by recently added": needs the folder's modification time

## 7. Done when
- The UI matches the reference mock at 1440–1500px width.
- Every existing action still works from its new location: change folder, rescan, run fixes, move to ingest, and the live log.
- Filters and counts are correct, and selecting a card updates the inspector.
- No console errors.
