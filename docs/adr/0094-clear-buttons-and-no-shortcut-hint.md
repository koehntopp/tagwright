# ADR 0094: Every text field can be cleared with an x; no ⌘K hint in the search

- **Status**: Accepted
- **Date**: 2026-11-22
- **Supersedes**: the ⌘K hint of [0031](0031-top-bar-again.md) ("the ⌘K hint from 1600 px up")

## Context

The owner found the ⌘K badge in the search field unnecessary, and asked that every text entry field have an x that deletes its content (in the web app and in the macOS port, which follows these ADRs).

## Decision

- The search field shows **no ⌘K hint**. The shortcut itself stays: ⌘K (Ctrl+K) still focuses the search, and the field's hover text still names it.
- Every **single-line text field** (text, search and password) shows an **x button** at its right end while it holds text and the pointer is over it or it has focus. Clicking it empties the field (exactly as deleting the text by hand: the change goes through the field's normal change handling) and keeps the focus in the field. It is a small lucide `X` (14 px, slate-400, slate-700 on hover), and the field reserves room for it so text never runs under it.
- Not cleared this way: **number** fields (track, disc and digit counts, seconds, cover sizes: narrow fields where a number is retyped), **read-only** and disabled fields, and the **lyrics** text area (one click would delete a whole song; select all and delete still works).
- The browser's own search-field cancel button is hidden, so a search field shows one x, not two.

## Consequences

- One consistent way to empty a field, also in table cells (tag editor, assignment dialogs) where selecting the text was fiddly.
- The x appears only on hover or focus, so tables full of fields do not show a column of x buttons at rest.
