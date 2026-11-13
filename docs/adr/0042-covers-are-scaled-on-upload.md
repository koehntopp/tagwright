# ADR 0042: A dropped or fetched cover is scaled to the limit at once

- **Status**: Accepted (the limit is a setting, default 1500: [0074](0074-maximum-cover-size-setting.md))
- **Date**: 2026-11-12
- **Supersedes**: the sentence in [0016](0016-cover-art.md) that an uploaded cover larger than `cover_max_size` is reduced only on a later run

## Context

An uploaded cover was embedded as it was and scaled only by the next Run fixes, so a large image sat in every file in between and the inspector showed the oversized pixel size. The owner is content with automatic scaling.

## Decision

- Uploading a cover (the drop, the upload button) and fetching one from Discogs make the picture in the files **at most `cover_max_size` (1500 px) on either side at once**, with the rule the pipeline uses (`pipeline.covers.resized`): JPEG quality 90, a PNG or other format becomes JPEG, transparency is flattened. An image within the limit is embedded unchanged (JPEG and PNG as they are, other formats as JPEG quality 95).
- Only the front cover is replaced; other pictures of the files stay as they are.
- The next run finds nothing to scale. The size shown in the inspector and the minimum-size check use the scaled size.

## Consequences

- A cover bigger than 1500 px cannot be kept at its original size through the app; the original stays wherever it came from.
- The status does not change by an upload alone: a scaled cover of at least the minimum size keeps an album Fixed.
