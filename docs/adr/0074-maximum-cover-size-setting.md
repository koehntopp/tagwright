# ADR 0074: The maximum cover size is a setting

- **Status**: Accepted
- **Date**: 2026-11-13
- **Supersedes in part**: [0042](0042-covers-are-scaled-on-upload.md) and [0016](0016-cover-art.md) (the fixed limit of 1500 px)

## Context

The minimum cover size is a setting ([0009](0009-settings-and-api-keys.md), [0016](0016-cover-art.md)) while the size covers are scaled down to was fixed at 1500 px (`Config.cover_max_size`).

## Decision

- A setting **"Maximum cover size (pixels)"** (`max_cover` in `settings.json`, Settings, General, next to the minimum), default **1500**. A cover larger than this on either side is scaled down to it with the rule of [0042](0042-covers-are-scaled-on-upload.md) (aspect ratio kept, JPEG quality 90, a PNG staying a PNG where it was): at upload and when a cover is fetched from Discogs, and by the cover step of a run (`fix_album`). Covers at or below it are left as they are.
- The value must be a whole number from 100 to 20000 and **not below the minimum cover size**: a cover scaled to the maximum must still pass the minimum check. A value that fails is refused with a message and nothing is saved.
- One value serves all three places: `app.py` builds the pipeline's configuration with it (`app_config()`).

## Consequences

- Changing the maximum does not touch covers that are already embedded; they are scaled the next time a run's cover step or an upload meets them, and only if larger.
- Lowering the minimum below the maximum, or raising the maximum above the minimum, is always allowed; the reverse is refused.
