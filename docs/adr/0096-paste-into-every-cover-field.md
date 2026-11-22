# ADR 0096: Paste an image into every cover field

- **Status**: Accepted
- **Date**: 2026-11-22
- **Amends**: [0092](0092-cover-controls-and-full-size-view.md), which named paste only for the front field

## Context

The owner reported that pasting does not work in the Back Cover, Leaflet and Media fields added by [0090](0090-artwork-types-and-cover-fields.md); only the Front Cover field listened for the paste key.

## Decision

- Every cover field takes focus on click and accepts **Cmd/Ctrl+V** with an image on the clipboard. The **Front Cover** is replaced, as before; in **Back Cover**, **Leaflet** and **Media** the pasted image is **appended**, like the **+** button. A paste without an image shows "No image on the clipboard".
- The **Paste image** menu item (clipboard API, [0016](0016-cover-art.md)) stays in the front field's menu only; the other fields get no menu.

## Consequences

- A set of booklet pages can be built by pasting one image after another into the Leaflet field.
- Replacing a single image in a multi-image field stays a drop action ([0092](0092-cover-controls-and-full-size-view.md)).
