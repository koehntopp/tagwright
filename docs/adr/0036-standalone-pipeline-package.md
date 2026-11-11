# ADR 0036: A standalone pipeline package; the discogs repository is no longer needed

- **Status**: Accepted (rollout in stages, see below)
- **Date**: 2026-11-11
- **Supersedes**, when the rollout reaches the cutover stage: [0004](0004-pipeline-engine-reuses-discogs-scripts.md) (the engine is the unchanged discogs scripts), [0012](0012-language-and-performance.md) (stay in Python; the DR step is now a Rust binary), the **Backend** bullet of [0005](0005-technology-stack-and-conventions.md) (one file), the discogs mount and `drmeter` binary of [0003](0003-deployment-web-app-in-docker.md), the config overlay of [0009](0009-settings-and-api-keys.md), and as history only [0025](0025-fingerprint-length-in-discogs-repository.md), [0027](0027-legacy-dynamic-range-tags-removed.md), [0032](0032-parallel-tag-writes-reopen-before-save.md) and [0033](0033-pipeline-tag-steps-run-in-sequence.md), which were changes to the discogs repository

## Context

Tagwright ran `nzbfix.py` from a checkout of the owner's discogs repository (0004). That repository also holds unrelated tools, a plain-text API key in `config.py`, a syslog/rclone configuration, and scripts that Tagwright only mirrored by hand (`clean()`, the tag lists, the lyrics rules). Every pipeline fix needed a second repository, a second ADR set and a `git push` before the Docker image could use it (0025, 0032, 0033). The owner decided that Tagwright must stand on its own, that the backend need not be one file, and that dynamic range is computed by the `drcalc` binary ([github.com/koehntopp/drcalc](https://github.com/koehntopp/drcalc)).

## Decision

- **Structure**: `app.py` stays the web layer and the launcher (`./app.py`, PEP 723 header). The pipeline is the package `pipeline/`, one module per step or shared helper, importing nothing from `app`:
  - `http.py` (one rate-limited JSON client), `discogs.py`, `musicbrainz.py`: the API clients, shared by the web layer and the steps, so the 1.1 s pacing holds across both;
  - `layout.py` (album folders), `tagio.py`, `config.py` (non-secret settings with the old defaults);
  - steps: `fixtags.py` (Discogs tags), `languages.py` (LYRICS_LANGUAGE), `covers.py` (cover resize), and in later stages the DR, ReplayGain, fingerprint and lyrics steps and `run.py`.
- **`fixtags` is refactored for Tagwright**: no command line, no `discogs_client` library (plain JSON from the Discogs API through `pipeline/discogs.py`), no `config.py`, no syslog; the Discogs data comes in through a `get` argument, so the logic is tested without a network. Every tag, rule and edge case of the original is kept ([0014](0014-internal-tag-editor.md)); `tests/test_fixtags_*.py` pin them.
- **Dynamic range** is computed by `drcalc` v0.1.0 (MIT) with `-w -q`; it writes `DYNAMIC_RANGE` and `ALBUM_DR` itself. Checked against the tags drmeter had written on three real albums (41 tracks): every track and album value identical. Unlike `calculate_dr.py` it recomputes all tracks of an album instead of only those without a tag (the result is deterministic). The Docker image takes the release binary for its architecture and verifies it against `SHA256SUMS`.
- **External tools** are found on `PATH`: `drcalc`, `rsgain`, `fpcalc` (and `dot_clean` where it exists). No Python is started per step.
- **Settings**: API keys stay in `settings.json` ([0009](0009-settings-and-api-keys.md)); the rest are constants in `pipeline/config.py` with the discogs defaults (cover limit 1500 px, MusicBrainz languages on, ReplayGain -14 LUFS, clip mode `a`, max peak -1.0 dBTP, true peak, skip when album gain exists). No new setting is shown in the UI.
- **Steps still run one after another** in the order of 0004/0033: `dot_clean`, DR, ReplayGain, fingerprints, Discogs tags, lyrics. A failing step is logged and the rest continue.

### Deliberate differences from the discogs scripts

- A Discogs `404` or other non-rate-limit HTTP error is **not retried** (the original slept 3 x 60 s on any error); a `429` or an empty body is retried 3 times after 60 s. MusicBrainz retries `429/502/503/504` 3 times after 5 s.
- One pacing for Discogs requests (1.1 s, 5 s pause below 3 remaining) instead of 1 s after each call.
- A PNG cover with transparency is converted to RGB before the JPEG resize (the original failed on it and left the cover alone).
- A FLAC with an existing but empty Vorbis comment is handled (the original `add_tags()` raised and skipped the file).
- Stale `ALBUM_COMPANY_*`, `ALBUM_CREDIT_*` and `ALBUM_IDENT_*` tags are compared case-insensitively. mutagen returns keys in lower case, which made the original treat them as stale on every run and rewrite every file each time.
- Messages go through `logging`; the job log shows them.

## Rollout

1. **Done with this ADR**: `pipeline/` with the shared clients, `fixtags`, languages, covers and their tests; `nzbfix` is still what "Run fixes" starts.
2. DR (`drcalc`), ReplayGain and fingerprint steps and the runner.
3. The lyrics step (`update_lyrics`, `lrc_format`, the lrclib client).
4. **Cutover**: "Run fixes" calls the pipeline in-process (Stop ends the child tools); `DISCOGS_DIR`, the config overlay and the discogs mount are removed; 0004 and 0012 are marked superseded; Docker ships `drcalc`, `rsgain` and `fpcalc`; AGENTS.md "Related code" is dropped.

## Consequences

- Tagwright needs no other repository; pipeline fixes are one commit and one ADR here.
- The hand-kept mirrors of `fixtags.py`, `bliss.clean()` and `lrc_count.py` can be replaced by imports from `pipeline/` once the matching step exists.
- Behaviour that the discogs scripts had and this list does not name is meant to be identical; a difference found later is a bug against this ADR.
