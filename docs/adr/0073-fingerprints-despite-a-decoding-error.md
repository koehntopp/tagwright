# ADR 0073: A fingerprint that fpcalc printed despite a decoding error is used

- **Status**: Superseded by [0075](0075-fingerprints-with-fpscan.md)
- **Date**: 2026-11-13
- **Supersedes in part**: [0036](0036-standalone-pipeline-package.md) (a step's tool failing on a non-zero exit code), for the fingerprint step

## Context

On the server a FLAC with a stray ID3v1 block after its last frame got no fingerprint: the newer ffmpeg in the image reports the trailing bytes as "invalid data", and `fpcalc` exits with code 2 although it has decoded the whole audio and printed `DURATION` and `FINGERPRINT`. Tagwright treated every non-zero exit as a failure and dropped the output, so the step failed and the track showed "No fingerprints". An older `fpcalc` on another machine exits 0 for the same file.

## Decision

- The fingerprint step takes the `FINGERPRINT=` line of `fpcalc`'s output whenever there is one, whatever the exit code. A non-zero exit with a fingerprint is logged as a **warning** (the exit code and fpcalc's message, which says what was wrong), and the file counts as fingerprinted.
- A non-zero exit **without** a fingerprint, or exit 0 without one, fails as before.

## Consequences

- A file with damage inside its audio could, if fpcalc still prints a fingerprint, be fingerprinted from what was readable. The warning names the file so it can be checked (`flac -t`).
- Albums that already lack the fingerprint of such a track get it with the next run of the fingerprint step.
