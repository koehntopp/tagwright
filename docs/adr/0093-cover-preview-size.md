# ADR 0093: Cover previews fill their field and show their size

- **Status**: Accepted
- **Date**: 2026-11-21
- **Supersedes**: the size placement of [0016](0016-cover-art.md) (W×H under the cover) for the four cover fields

## Context

With the four cover fields of [0090](0090-artwork-types-and-cover-fields.md) the old cover button's size line disappeared. An uploaded cover was also letterboxed inside its field (`object-contain`), leaving large white margins that looked like the image had not been applied.

## Decision

- Each cover field that holds an image shows its **W×H** in the field header, on the right of the type name, with the byte size in the image's hover text. This replaces the size line under the single cover of [0016](0016-cover-art.md).
- The preview image occupies a full-width **square box** and **fills it** (`object-cover`), so a large cover occupies the field instead of floating in white space. The full image is still available through the double-click view of [0092](0092-cover-controls-and-full-size-view.md).
- The minimum-size warning of [0016](0016-cover-art.md), the album-level writes of [0090](0090-artwork-types-and-cover-fields.md) and the crop-free full-size view are unchanged.

## Consequences

- The size is visible even when several images make the field busy, without adding a line under each preview.
- A non-square image is cropped in the field preview; double-click to see it whole.
