# ADR 0072: Offer to delete the album's staging folder after a move

- **Status**: Accepted
- **Date**: 2026-11-13
- **Supersedes in part**: [0011](0011-ingestion-move.md) (the files that stay behind in the staging folder stay there for good)

## Context

"Move to library" moves the songs only ([0011](0011-ingestion-move.md), [0037](0037-library-watcher-and-layout.md)); the cover, rip logs, scans and the folder itself stay in the staging folder, which fills up with emptied album folders.

## Decision

- A setting **"Offer to delete the album's folder after a move"** (`delete_after_move` in `settings.json`, a checkbox in Settings, General; off by default, [0009](0009-settings-and-api-keys.md)).
- With it on, the Move dialog says that the leftovers can be deleted afterwards (with it off it says they stay in the staging folder), and after a successful move a dialog **"Delete the folder?"** opens. It names the album's folder in the staging folder, says how many files (and how many bytes) and how many **subfolders** are left, and lists every subfolder (empty ones too) and every file below it with its size (the first 300 of each; the rest are counted). The text says that the subfolders are deleted too. Buttons: **Delete** and **Cancel**. Cancel leaves everything as it is; nothing is deleted without Delete.
- `GET /api/folder?path=` returns that list. `POST /api/folder/delete` deletes the folder with everything in it, and is the only endpoint that deletes more than a cover ([0024](0024-delete-cover-removes-folder-image.md)). It refuses (400, 404 or 409) when: the path is not **inside** the staging folder (the staging folder itself and the library are refused); the setting is off; a job is running ([0008](0008-job-model.md)); or **any song is still in the folder or below it**, whatever the dialog showed. The folder is deleted with its contents, links are not followed, and the deletion is logged ([0064](0064-logging-and-syslog.md)).
- The list counts hidden files and the sizes come from the files themselves, at the time the dialog opens and again when Delete is pressed (the check for songs).

## Consequences

- A deletion cannot be undone by Tagwright; the dialog is the only confirmation.
- Folders of albums that were not moved by Tagwright are not offered; the dialog appears only right after a move.
