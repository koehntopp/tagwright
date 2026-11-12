# ADR 0038: Staging and Library views; one name for each folder

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes**: the rule in [0007](0007-trust-boundary-and-secrets.md) that `safe()` accepts paths under the input folder only (it now accepts the staging and the library folder), and the Filenames step and rename of [0054](0054-album-status-and-steps-consolidated.md) / [0010](0010-bliss-file-naming.md) where they say the name is the bliss name (it is the file name row of the layout template, which is the bliss name by default)

## Context

Since [0037](0037-library-watcher-and-layout.md) the output folder is the library and the owner fixes details of albums that are already in it (tags, covers, lyrics, a wrong version). The web UI only browsed the input folder. The two folders also had several names (input, output, ingest, library).

## Decision

- **Names**: the folder albums are fixed in is the **Staging folder**, the folder they end up in is the **Library folder**. Settings, dialogs and messages use these two names (the keys in `settings.json` stay `input` and `output`). Use case UC-15 (added to [0002](0002-purpose-scope-and-use-cases.md)): fix details of albums that are already in the library with the same tools as in staging.
- **A switch in the top bar**, to the left of the search box and as tall and round as it: the word **Staging**, a toggle, the word **Library** (the chosen side is dark, the thumb is on the right for the library). It chooses which folder the card board lists; the filters, search, inspector and dialogs work the same in both. The choice is remembered in the browser. `GET /api/albums?path=<folder>` lists any folder under the staging or the library folder.
- **`safe()`** accepts a path under the staging folder or under the library folder; every other path is still refused (400). Endpoints that write keep the 409 rule while a job runs.
- **Library albums**: Run fixes, the tag editor, covers, lyrics and the Discogs and MusicBrainz tools work as in staging. **Move to library** is refused for an album that is already in the library (409; the move preview says so). After a write the album's folders are listed again by the watcher at its next pass (`Library.refresh`), so a changed tag that changes the album's path moves the files after the cooldown ([0037](0037-library-watcher-and-layout.md)).
- **File names come from the layout**: the Filenames step compares each file's name with the file name row of the library template, and the rename after a run, a tag save or an assignment writes that name. With the default template that is the bliss name; with another template the rename and the watcher agree, so they never rename against each other.

## Consequences

- A library album edited in the UI is changed on the library volume; the watcher may move it afterwards. Turn Apply off in Settings, Library to review first.
- The Filenames step of a library album can be open after a template change until the watcher has renamed its files.
