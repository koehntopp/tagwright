# ADR 0008: Job model: one job at a time, queue, polling, write lock

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The pipeline is heavy (CPU, disk, rate-limited networks) and edits the same files the UI edits.

## Decision

- **One job at a time.** `POST /api/run` takes `{path}` or `{paths}`; if a job is running it returns 409. "Run all ready" submits every `ready` album as one queue processed in order by a single worker thread; a failed album is logged and the queue continues. Job state is `idle`, `running`, `done` or `failed`.
- **Log**: output lines of all runs accumulate in memory in one list (not cleared per run). Clients poll `GET /api/job?since=<offset>` once per second while a job runs and receive only new lines. The running album is re-read every third poll so its steps update live.
- **Write lock**: while any job is running, every endpoint that changes files or settings returns 409: move, settings, track assignment, track edit, tag editor save, overrides, cover upload.
- **After a successful run** (exit code 0) the files are renamed ([0010](0010-bliss-file-naming.md)).
- State is in process memory; a server restart loses the log and the queue. The running subprocess is not resumed.

## Consequences

- A long queue blocks all editing; accepted for safety.
- Per-album concurrency (overlapping albums during rate-limit waits) was considered and not built.
