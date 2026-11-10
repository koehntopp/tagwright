# ADR 0008: Job model: one job at a time, queue, polling, write lock

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

The pipeline is heavy (CPU, disk, rate-limited networks) and edits the same files the UI edits.

## Decision

- **One job at a time.** `POST /api/run` takes `{path}` or `{paths}`; if a job is running it returns 409, and an album with a blocking issue (status `needs`, [0006](0006-status-model-and-pipeline-steps.md)) is refused with 409 as well. A `{paths}` request is one queue processed in order by a single worker thread; a failed album is logged and the queue continues. The UI has no "Run all ready" button (removed, [0022](0022-top-bar-instead-of-sidebar.md)) and starts one album at a time with Run fixes; the queue form stays in the API. Job state is `idle`, `running`, `done`, `failed` or `stopped`.
- **Log**: output lines of all runs accumulate in memory in one list (not cleared per run). Clients poll `GET /api/job?since=<offset>` once per second while a job runs and receive only new lines. The running album is re-read every third poll so its steps update live.
- **Write lock**: while any job is running, every endpoint that changes files or settings returns 409: move, settings, track assignment, track edit, tag editor save, overrides, cover upload.
- **Stop**: `POST /api/stop` (the **Stop** button in the top bar, shown only while a job runs) clears the queue and ends the running `nzbfix` together with every tool it started. `nzbfix` runs in its own process group (`start_new_session`); the group gets SIGTERM and, if still alive after 10 s, SIGKILL. The current album's log ends with `-- stopped by user`, it is not renamed, queued albums never start, and the job state becomes `stopped` (amber dot, "Last run stopped"). With no job running it answers 409. Caveat: stopping can interrupt a tag write in the middle of a file; run the album again (the steps are idempotent) and check it before ingest.
- **After a successful run** (exit code 0) the files are renamed ([0010](0010-bliss-file-naming.md)).
- State is in process memory; a server restart loses the log and the queue. The running subprocess is not resumed.

## Consequences

- A long queue blocks all editing; accepted for safety.
- Per-album concurrency (overlapping albums during rate-limit waits) was considered and not built.
