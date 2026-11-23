# ADR 0103: The library watcher removes empty folders it finds

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0037](0037-library-watcher-and-layout.md) (empty folders are removed only right after a move out of them)

## Context

The watcher moved Phil Collins, *Face Value* (Blu-ray) from `Face_Value_2026_DR13_Blu_ray_BD25_1080P24` to `..._603497807352` after a new Discogs release changed its catalog number. The old album folder stayed behind with four empty `Disc 1` … `Disc 4` folders. 0037 removes a folder only when it is empty right after the move that emptied it; a folder emptied later (here the disc folders, whose `folder.jpg` were gone only afterwards) is never looked at again. The owner wants such folders removed, but never one that still has music below it.

## Decision

- On every **full pass** of the watcher (the first pass after a start, the daily sweep, and *Re-analyze* in the Library dialog), with *Apply* on, `remove_empty_dirs` (`library/executor.py`) removes every folder below the library root that holds nothing but litter (`.DS_Store`, `._*`, `Thumbs.db`, `desktop.ini`, as in 0037) and folders of that kind, deepest first.
- A folder that holds any other file, music or not (a scan, a booklet PDF, a `folder.jpg`), stays, and so do all folders above it. The library root is never removed. Hidden folders (a name starting with a dot) are neither entered nor removed.
- It runs under the same lock as the moves, so it never races *Move to library*. The activity log says `removed N empty folder(s) left behind`; report-only mode removes nothing.

## Consequences

- Leftover album and disc folders disappear at the next full pass (after a restart, within a day, or at once with *Re-analyze*).
- An empty folder created by hand in the library is removed too.
