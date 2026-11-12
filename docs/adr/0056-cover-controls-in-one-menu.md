# ADR 0056: Cover controls in one menu, with the size warning on the cover

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0016](0016-cover-art.md) (the icon row under the cover: upload, the two search links and delete) and the red delete icon of [0024](0024-delete-cover-removes-folder-image.md)

## Context

Five controls sat under the cover at all times, including a permanent red delete icon; the two search sites were 14 px logos that needed a hover to understand, and a cover that was too small was only flagged in the issue list.

## Decision

- Under the cover: a **size pill** (`W×H`, or "no cover"; its tooltip says embedded or folder image and the file size) and a **"…" button**. The button opens a menu: **Upload image**, **Search musichoarders** and **Search albumartexchange** (the same links as before, with their logos), and, when there is a cover, **Remove cover** in red, which opens the same confirmation ([0024](0024-delete-cover-removes-folder-image.md)). The menu closes on a click elsewhere, on Escape and after any item.
- A cover below the minimum size, or none, with the issue line of [0016](0016-cover-art.md) present: the cover gets a **dashed amber outline** and the pill turns **amber** with a warning icon; its tooltip is the issue text. Nothing else around the cover is coloured.
- Dropping an image on the cover still replaces it, with the same drag highlight.
