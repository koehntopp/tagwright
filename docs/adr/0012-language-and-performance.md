# ADR 0012: Stay in Python; speed up compute inside the discogs scripts

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

A rewrite in Go or Rust was analysed. Measurements on a 12-core Mac with a 20-track, 345 MB album: dynamic range 4.3 s, fingerprints 2.8 s, `rsgain` 4.5 s (each about one core), app scan 0.19 s cold / 0.03 s cached for 6 albums, about 0.15 to 0.23 s `uv` start-up per script. `nzbfix` runs the three compute stages in parallel. `fixtags` and `update_lyrics` are bound by remote rate limits (Discogs 60 requests/min, MusicBrainz 1/s, lrclib deliberately one request at a time), not by language. `drmeter` is about 60 lines of numpy over libsndfile; `rsgain` and `fpcalc` are already native.

## Decision

- Tagwright and the pipeline stay in Python. A rewrite gains little for the cost of re-validating tag output.
- Compute speed-ups are made in the discogs repository, not in Tagwright, and must keep the output identical:
  - `calculate_dr.py` decodes tracks in a process pool and writes tags sequentially (4.2 s to 0.9 s on the test album; identical `DYNAMIC_RANGE` and `ALBUM_DR`).
  - `calculate_fp.py` runs `fpcalc` in a thread pool (2.8 s to 0.6 s).
  - `rsgain -m N` was tried and gave no speed-up for one album, so it is not used.
- A Rust port of the DR algorithm remains possible if DR is still the bottleneck; it is acceptable only with bit-identical results across the library.
- A Go/Rust rewrite of the whole app is reconsidered only for a single static binary (no Python on the server).

## Consequences

- Per-album compute is limited by `rsgain` (about 4.5 s). Further gains would need splitting an album across `rsgain` runs, which changes how album gain is computed and needs its own decision.
