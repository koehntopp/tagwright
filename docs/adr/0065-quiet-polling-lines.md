# ADR 0065: Successful polls stay out of the access log

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0064](0064-logging-and-syslog.md) ("uvicorn's access lines stay as they are")

## Context

The page polls `GET /api/library` and `GET /api/job` every few seconds. Their access lines were most of what the container printed, and, where Docker's own syslog driver ships stdout to a collector, hundreds of rows an hour that hid jobs, moves and errors.

## Decision

- The access log drops the line of a **successful** (2xx or 3xx) `GET` of `/api/library` or `/api/job`. Every other request, and a poll that fails, is still logged. `pipeline/logconfig.py` gives uvicorn its logging configuration with this filter on the access handler.
- Nothing else about logging changes: standard output, the optional `SYSLOG_HOST` and the program's own lines are as in [0064](0064-logging-and-syslog.md). A host whose container output already reaches a syslog server through Docker's log driver does not need `SYSLOG_HOST`, because it would send every line twice.
