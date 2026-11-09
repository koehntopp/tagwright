# Architecture decision records

Every decision that shapes Tagwright is recorded here. Process and rules: [ADR 0001](0001-record-architecture-decisions.md). Agents must follow [AGENTS.md](../../AGENTS.md).

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-purpose-scope-and-use-cases.md) | Purpose, scope and use cases (UC-1 to UC-10) | Accepted |
| [0003](0003-deployment-web-app-in-docker.md) | Deployment: a web app in Docker on a Linux server | Accepted |
| [0004](0004-pipeline-engine-reuses-discogs-scripts.md) | The pipeline engine is the unchanged discogs scripts | Accepted |
| [0005](0005-technology-stack-and-conventions.md) | Technology stack and code conventions | Accepted |
| [0006](0006-status-model-and-pipeline-steps.md) | Status comes from FLAC tags; six pipeline steps | Accepted |
| [0007](0007-trust-boundary-and-secrets.md) | Trust boundary, no authentication, secrets | Accepted |
| [0008](0008-job-model.md) | Job model: one job at a time, queue, polling, write lock | Accepted |
| [0009](0009-settings-and-api-keys.md) | Settings and API keys | Accepted |
| [0010](0010-bliss-file-naming.md) | Bliss file naming after fixes and edits | Accepted |
| [0011](0011-ingestion-move.md) | Moving fixed albums to the ingest folder | Accepted |
| [0012](0012-language-and-performance.md) | Stay in Python; speed up compute inside the discogs scripts | Accepted |
| [0013](0013-discogs-track-assignment.md) | Discogs release search and track assignment | Accepted |
| [0014](0014-internal-tag-editor.md) | Internal tag editor; what is editable and what is Discogs-owned | Accepted |
| [0015](0015-track-playback-and-track-edit.md) | Track playback and per-track edit | Accepted |
| [0016](0016-cover-art.md) | Cover art: display, size warning, replacement | Accepted |
| [0017](0017-ui-layout-and-design-system.md) | UI layout and design system | Accepted |
| [0018](0018-verification.md) | Verification without touching real data | Accepted |
| [0019](0019-version-control-and-releases.md) | Version control and releases | Superseded by 0020 |
| [0020](0020-work-directly-on-main.md) | Work directly on main; no feature branches | Accepted |
| [0021](0021-lrclib-lyrics-search.md) | Lyrics search on lrclib.net in the track editor | Accepted |
| [0022](0022-top-bar-instead-of-sidebar.md) | Top bar instead of a sidebar | Accepted |

## Which ADR covers what

| If you change... | Read first |
|------------------|-----------|
| what the app is for, a new feature | 0002 |
| Docker, environment variables, mounts | 0003 |
| running `nzbfix`, anything about the discogs scripts | 0004, 0012 |
| dependencies, build, code style, CSS build | 0005 |
| statuses, steps, lyrics rules, scan cache | 0006 |
| paths, endpoints, secrets, access | 0007 |
| jobs, queue, log, endpoints that write | 0008 |
| settings dialog, API keys, config overlay | 0009 |
| file names, `rename_files`, `clean()` | 0010 |
| Move to ingest | 0011 |
| Discogs search, track assignment | 0013 |
| tag editor, override pencils, which tags are editable | 0014 |
| play button, track edit dialog, lyrics editing | 0015, 0021 (artist field, lrclib search) |
| cover display, size warning, cover upload | 0016 |
| layout, colours, widths, dialogs, `index.html` styling | 0017, 0022 (top bar replaces the sidebar) |
| how to test | 0018 |
| commits, pushing, tags (no branches) | 0020 |
