# ADR 0032: Parallel pipeline scripts reopen a file before saving (discogs repository change)

- **Status**: Accepted
- **Date**: 2026-11-10

## Context

`nzbfix.py` runs `calculate_dr.py`, `rsgain` and `calculate_fp.py` at the same time on the same files ([0004](0004-pipeline-engine-reuses-discogs-scripts.md)). The two Python scripts both did, per file: open it with mutagen (`FLAC(path)`, reading the tags), wait for the worker that decodes the audio, then `audio.save()`. Whatever the other script wrote to that file during the wait was erased by the save of the stale copy.

The wait is longest for the first file: both scripts open it at the start and block on the first, slowest decode. So the first track very often lost its `ACOUSTID_FINGERPRINT` (the fingerprint script logged it as generated) or its `DYNAMIC_RANGE`, and the album stayed Ready. The owner noticed "fingerprints often fail on the first track". Reproduced on a scratch copy: with the three tools in parallel the first file lacked its fingerprint in two of two runs; `calculate_dr.py` with `calculate_fp.py` alone showed it, `rsgain` with `calculate_fp.py` and `calculate_fp.py` alone did not.

## Decision

- In the discogs repository, `calculate_fp.py` and `calculate_dr.py` **reopen the FLAC file after the worker result has arrived and immediately before the tag write**, so the save starts from the tags on disk at that moment. No change to what is written, to the order of steps or to `nzbfix.py` ([0004](0004-pipeline-engine-reuses-discogs-scripts.md): steps are not reordered or skipped).
- Done at the owner's request ("yes, fix it"); this ADR records why the discogs scripts changed.
- Verified on a scratch copy of a 22-file album: tags stripped, the three tools started in parallel as `nzbfix` does, three runs; every file had fingerprint, DR and ReplayGain each time.

## Consequences

- A race window of milliseconds remains between the reopen and the save; it is not closed by locking. If a tag still goes missing after a run, the next Run fixes fills it (the scripts only write what is missing).
- Any new pipeline script that writes tags while others run in parallel must follow the same rule: do not hold tags read before a long wait.
