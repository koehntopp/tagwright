# ADR 0033: Dynamic range, ReplayGain and fingerprints run in sequence (discogs repository change)

- **Status**: Accepted (history: a change to the discogs repository, which Tagwright no longer uses, [0036](0036-standalone-pipeline-package.md))
- **Date**: 2026-11-10
- **Supersedes**: the word "in parallel" in [0004](0004-pipeline-engine-reuses-discogs-scripts.md) (the steps and their order are unchanged)

## Context

[0032](0032-parallel-tag-writes-reopen-before-save.md) found that `calculate_dr.py`, `rsgain` and `calculate_fp.py`, started together by `nzbfix.py`, overwrote each other's tags (the first track often lost its fingerprint). Reopening the file before each save only shrinks that window; all three tools write tags into the same files, so any overlap can lose a tag. The owner asked whether running them in sequence would be safer.

Measured on a scratch copy of a 22-file album on a 12-core Mac (local disk, two runs each): 15 s in parallel, 17 s in sequence. Each tool already uses all cores, so parallel gains little there; over a network share the overlap of reads could matter more, which was not measured (ADR 0018: no tests on the real library).

## Decision

- In the discogs repository `nzbfix.py` starts `calculate_dr`, `rsgain` and `calculate_fp` **one after another** and waits for each, in the same order as before; `fixtags` and `update_lyrics` follow as before. Failures are logged as before ("<name> exited with code N") and do not stop the pipeline. Ctrl+C kills the running child.
- The reopen-before-save change of 0032 stays as a second safeguard.
- Done at the owner's request ("Yes, sequential").
- Verified: `nzbfix.py` run on a scratch copy of a 22-file album with the DR, ReplayGain and fingerprint tags stripped: steps finished in order, every file had fingerprint, DR and ReplayGain tags, about 20 s in total.

## Consequences

- A Run fixes may take a few seconds longer per album; no tag is lost to a race between these steps.
- Tagwright's step ticks (the inspector refreshes every 3 s while a job runs) show the steps becoming done one at a time.
