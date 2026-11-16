# ADR 0056: Cover controls in one menu, with the size warning on the cover

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0016](0016-cover-art.md) (the icon row under the cover: upload, the two search links and delete) and the red delete icon of [0024](0024-delete-cover-removes-folder-image.md)

## Context

Five controls sat under the cover at all times, including a permanent red delete icon; the two search sites were 14 px logos that needed a hover to understand, and a cover that was too small was only flagged in the issue list.

## Decision

- Under the cover: a **size pill** (`W×H`, or "no cover"; its tooltip says embedded or folder image and the file size) and a **"…" button**. The button opens a menu: **Upload image**, **Paste image** (clipboard icon), **Search musichoarders** and **Search albumartexchange** (the same links as before, with their logos), and, when there is a cover, **Remove cover** in red, which opens the same confirmation ([0024](0024-delete-cover-removes-folder-image.md)). The menu closes on a click elsewhere, on Escape and after any item.
- A cover below the minimum size, or none, with the issue line of [0016](0016-cover-art.md) present: the cover gets a **dashed amber outline** and the pill turns **amber** with a warning icon; its tooltip is the issue text. Nothing else around the cover is coloured.
- Dropping an image on the cover still replaces it, with the same drag highlight.
- **Paste image** takes the image on the clipboard and sends it through the same `PUT /api/cover` and scaling as a drop ([0042](0042-covers-are-scaled-on-upload.md)). It is a menu item only: there is no global paste key, so pasting into a text field never touches the cover. Where the browser allows reading the clipboard (https, localhost) the item reads it directly; over plain http on the LAN there is no clipboard API, so the item focuses the cover (a light ring) and says "Press Cmd/Ctrl+V to paste the image"; the cover accepts the paste only while it has focus. No image on the clipboard gives a toast.

- **Progress**: while a dropped or uploaded image is being scaled and embedded (a few seconds for a large image), the cover shows a spinner over it, the size pill says "Processing…", the Tags and cover step circle spins, and a second drop is ignored until it is done.
