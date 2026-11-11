# ADR 0036: A standalone pipeline package; the discogs repository is no longer needed

- **Status**: Accepted (rolled out, see below)
- **Date**: 2026-11-11
- **Supersedes**: [0004](0004-pipeline-engine-reuses-discogs-scripts.md) (the engine is the unchanged discogs scripts), [0012](0012-language-and-performance.md) (stay in Python; the DR step is now a Rust binary), the **Backend** bullet of [0005](0005-technology-stack-and-conventions.md) (one file), the discogs mount and `drmeter` binary of [0003](0003-deployment-web-app-in-docker.md), the config overlay of [0009](0009-settings-and-api-keys.md), and as history only [0025](0025-fingerprint-length-in-discogs-repository.md), [0027](0027-legacy-dynamic-range-tags-removed.md), [0032](0032-parallel-tag-writes-reopen-before-save.md) and [0033](0033-pipeline-tag-steps-run-in-sequence.md), which were changes to the discogs repository

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

All four stages are done:

1. `pipeline/` with the shared clients, `fixtags`, languages, covers and their tests.
2. The DR (`drcalc`), ReplayGain and fingerprint steps and the runner.
3. The lyrics step (`lyrics.py`, `lrc_format.py`, `lrclib.py`).
4. **Cutover**: "Run fixes" calls `pipeline.run.run_album` in the job thread; what the pipeline logs reaches the job log through a handler; Stop sets the run's flag and ends the child tools (SIGTERM, SIGKILL after 10 s). `app.py` uses the shared Discogs and MusicBrainz clients and `pipeline.naming` / `pipeline.layout`; `DISCOGS_DIR`, the config overlay and the discogs mount are removed; the Dockerfile installs `drcalc` from the verified release.

Verified on a scratch copy of one real album (11 tracks, Discogs lookup with the owner's key, real `drcalc`, `rsgain`, `fpcalc`): after stripping the DR, ReplayGain, fingerprint and all Discogs-written tags, one "Run fixes" restored **every tag identical** to what the discogs pipeline had written (1285 tags; the only difference was `ORIGINALYEAR`, an old tagger tag the test itself had removed). Not verified: the Docker image (never built), the lyrics step against the live lrclib service, a multi-disc album end to end.

### Changes the owner has to know about

- **The Discogs API key must be in Settings.** The discogs `config.py` is no longer read, so a key that only lived there is no longer found. Enter it once in the Settings dialog (it is stored in `data/settings.json`, [0009](0009-settings-and-api-keys.md)); the old plain-text copy in the discogs repository can then be rotated.
- A step that fails (for example `drcalc` on a track shorter than 12 s) is logged and the album is shown as failed, but the remaining steps and the file rename still run. The old `nzbfix` returned success in this case.
- The lyrics cache export (`{id}_{track}.lrc|txt` files in a `lyrics/` folder) is not carried over; the lyrics live in the tag only.
- `data/overlay/` (the generated config copy) is obsolete and can be deleted.
- `/api/job` has a `step` field: the pipeline step running now, named as the UI's pipeline row names it (`Discogs tags` is `Tags and cover`, the rename is `Filenames`). The row pulses that step. The old UI pulsed the first step that was not done, which stopped working once steps could re-run a step that was already done.

## Consequences

- Tagwright needs no other repository; pipeline fixes are one commit and one ADR here.
- The hand-kept mirrors are gone: `clean()` and the bliss names live in `pipeline/naming.py`, the Discogs tag lists are checked against `pipeline/fixtags.py` by `tests/test_tag_contract.py`.
- Behaviour that the discogs scripts had and this list does not name is meant to be identical; a difference found later is a bug against this ADR.
