# ADR 0092: Compact cover controls and a full-size view

- **Status**: Accepted
- **Date**: 2026-11-21
- **Supersedes**: the control bullets of [0090](0090-artwork-types-and-cover-fields.md) (Replace buttons and the action labels)

## Context

The four cover fields of [0090](0090-artwork-types-and-cover-fields.md) put arrows, **Replace**, **Delete** and **+ Add** on one narrow row. At the inspector's width the labels wrap and the row is hard to read. Dropping an image on a field and pasting into the front field already replace the selected image, so a separate Replace button adds little. The owner also wants to look at an image full size without leaving the inspector.

## Decision

- A filled cover field has no **Replace** button: **drop an image on the field** (or paste in the front field, or use the front field's Upload menu item) to replace the selected image. An empty field keeps an **Upload** button. **Delete** stays; the multi-image fields keep the `‹ n / total ›` arrows and a compact **+** button to append an image. Labels do not wrap.
- **Double-click the image in a field** opens it in a full-size modal over the app. The modal closes on any click and on Escape; it has no other controls. The same applies to a folder image shown in the front field.
- Picture types, album-level writes, size scaling, sorting, colours and all endpoints stay as in [0090](0090-artwork-types-and-cover-fields.md).

## Consequences

- The action row fits comfortably in each of the four columns.
- Replacing an image is a drag-and-drop or paste action, so a keyboard-only user still has the front field's Upload menu item; for the other fields the + button appends and Delete removes, which is enough to curate a set.
- The full-size view is read-only and never changes the embedded art.
