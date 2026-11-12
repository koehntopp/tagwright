# ADR 0066: Renames, tag edits and lyrics edits are logged; LOG_LEVEL

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: [0064](0064-logging-and-syslog.md) (what is logged, and the fixed info level)

## Context

The rename after a run, an edit or an assignment returned its lines to the UI only; a tag save logged counts but not which fields changed; a lyrics edit was not logged. For a library of files that is the trail one wants after an unexpected change.

## Decision

- **Renames**: `rename_album_files` (the one place the program renames after a run, an edit or an assignment) logs one INFO line per album, "renamed N file(s) in <album>", and each file's line at DEBUG. A rename that would overwrite an existing file is a WARNING.
- **Tag edits**: INFO "tags saved: <album>: FIELD='value', ...; N track(s) edited" with the album fields and their new values; each edited track (file, title, disc, track, artist) at DEBUG.
- **Lyrics edits**: INFO "lyrics edited (N chars)" or "lyrics removed" with the album and file.
- **`LOG_LEVEL`** (`DEBUG`, `INFO`, `WARNING` or `ERROR`; default `INFO`) sets the level of the program's loggers, so `DEBUG` shows the per-file lines without a rebuild. A bad value is a start-up error. It is optional ([0055](0055-no-default-paths.md) is about paths).
- The lines hold tag text such as titles and file names, as the existing ones hold album names; they never hold an API key ([0007](0007-trust-boundary-and-secrets.md)).

## Consequences

- The job log in the UI is unchanged: these lines use the `app` logger, which is not copied into it.
