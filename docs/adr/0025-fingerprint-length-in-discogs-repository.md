# ADR 0025: Fingerprints read the first 120 seconds (change in the discogs repository)

- **Status**: Accepted (history: a change to the discogs repository, which Tagwright no longer uses, [0036](0036-standalone-pipeline-package.md))
- **Date**: 2026-11-09

## Context

[0004](0004-pipeline-engine-reuses-discogs-scripts.md) forbids editing the discogs repository unless the owner asks. The owner asked. `calculate_fp.py` called `acoustid.fingerprint_file(..., maxlength=10000)`, which makes `fpcalc` decode the whole file. On `Billy_Joel/Songs_In_The_Attic_2013_DR12_MFSL_SACD_UDSACD_2092/01_05_She_s_Got_A_Way.flac` (88.2 kHz, 24 bit) that decode ends with "Error decoding audio frame" and exit status 3, every run, so the Fingerprints step ([0054](0054-album-status-and-steps-consolidated.md)) stayed at 10 of 11 tracks. `flac -t` and `ffmpeg` decode the file without errors.

## Decision

- In the discogs repository, `calculate_fp.py` uses `maxlength=120`. AcoustID matches on the first 120 seconds, so lookups are unaffected. Verified: the failing file fingerprints with 120 and fails with 10000.
- Tagwright code is unchanged; it runs the script as before.

## Consequences

- New fingerprints are shorter than those written earlier with the whole-file length. Existing tags are not recomputed.
