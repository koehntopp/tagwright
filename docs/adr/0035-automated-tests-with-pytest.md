# ADR 0035: Automated tests with pytest on synthetic albums

- **Status**: Accepted
- **Date**: 2026-11-11
- **Supersedes**: nothing; it is the ADR for the test framework that [0018](0018-verification.md) asks for ("when automated tests are added, they follow this rule and need an ADR for the framework"). 0018 and the "no test framework" consequence of [0005](0005-technology-stack-and-conventions.md) stand for manual verification of the UI and the real pipeline.

## Context

Verification was manual ([0018](0018-verification.md)). The status model ([0006](0006-status-model-and-pipeline-steps.md)), bliss naming ([0010](0010-bliss-file-naming.md)), the job model ([0008](0008-job-model.md)) and the move ([0011](0011-ingestion-move.md)) are rules that regress quietly. They can be checked on small synthetic files, without the real tools and without the network.

## Decision

- **Framework**: pytest, with FastAPI's `TestClient` (needs `httpx`). Tests live in `tests/` and import `app.py` as the module `app`.
- **Dependencies** are declared in `pyproject.toml` under `[dependency-groups] test`: the runtime dependencies of `app.py` (also listed in its PEP 723 header, which stays the source for running the app) plus `pytest`, `httpx`, `numpy` and `soundfile` (the last two only to write silent FLAC fixtures). Run with `uv run --group test pytest`.
- **No real data** (0018): `tests/conftest.py` sets `STAGING_FOLDER`, `LIBRARY_FOLDER`, `DATA_DIR` and `DISCOGS_DIR` to a temporary directory **before** importing `app.py` (so the real `data/settings.json` is never read), then points `ROOT`, `INGEST` and `SCRIPTS` at a fresh `tmp_path` for every test and asserts it is under it. FLAC files are generated (0.2 s of silence plus tags); no music file is committed.
- **The network and the tools are faked**: the job tests replace the pipeline steps (`pipeline.run.STEPS`) with small functions that write the tags the real steps write; the step tests use fake `drcalc`, `rsgain` and `fpcalc` scripts and a fake Discogs, MusicBrainz and lrclib (injected `get` and opener arguments). Tests that need the real `drcalc`, `fpcalc` or `rsgain` run only when the binary is on `PATH` and are skipped otherwise.
- **What is covered**: naming and lyrics rules (`clean`, `bliss_name`, `bliss_album`, `lyric_kind`, `rename_files`); album discovery and `safe()`; the six steps, issue lines and album status; the job model (run, queue, failure, 409 while running, stop); Move to ingest (only `fixed`, never overwrites, small cover blocks it).
- **Not covered**: the UI, the Discogs, MusicBrainz and lrclib endpoints, cover upload, the real Discogs, MusicBrainz and lrclib services. These stay manual per 0018; the change rule "a change to tag output is compared before and after on a copy" is unchanged.
- **Rule for new code**: a change to the behaviour above comes with a test that fails without it. Tests follow ADR 0034 (ruff, tabs, annotations).

## Consequences

- `uv run --group test pytest` is part of "done" for a Python change, next to the ruff checks ([AGENTS.md](../../AGENTS.md)).
- The runtime dependencies appear in two places (PEP 723 header and the test group); keep them equal.
- The tests run in a second or two and need no network.
