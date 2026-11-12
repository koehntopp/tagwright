# ADR 0064: Logging to standard output, and to syslog when SYSLOG_HOST is set

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

The program had no log. The container showed uvicorn's access lines and warnings; the log of a run existed only in the in-memory job log that the UI polls, and the library watcher's activity only in memory. A restart or a redeploy lost them, and a failed run on the server left no record.

## Decision

- Three loggers are the program's own: `app` (jobs, moves, assignments, tag, cover and settings saves, start-up), `pipeline` (the steps) and `library` (the watcher: moves, renames, problems). At start-up (`pipeline/logconfig.py`) they log at info level to **standard output** with a timestamp, so `docker logs` and Dozzle show them. uvicorn's access lines stay as they are and are not sent to syslog.
- **`SYSLOG_HOST`** turns syslog on; the same lines also go to that host. `SYSLOG_PORT` (default 514) and `SYSLOG_PROTOCOL` (`udp`, the default, or `tcp`) say where and how. Messages use the user facility, the program name `tagwright` and the level as priority; TCP lines end with a newline. With `SYSLOG_HOST` unset nothing is sent. A bad port or protocol is a start-up error; a TCP server that is not reachable is logged and the program starts with standard output only. Only the standard library is used.
- Lines carry album folder names, file counts and library paths. They never carry an API key ([0007](0007-trust-boundary-and-secrets.md)): a settings save logs "settings saved" and nothing else of it.
- UDP can lose messages; TCP does not, at the cost of a reconnect after the server was away.

## Consequences

- The job log in the UI is unchanged. Its lines are now also in the container log, as `pipeline.*` lines.
- Syslog is not authenticated or encrypted: use it on a trusted network.
