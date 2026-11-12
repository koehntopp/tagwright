# Architecture decision records

Every decision that shapes Tagwright is recorded here. Process and rules: [ADR 0001](0001-record-architecture-decisions.md). Agents must follow [AGENTS.md](../../AGENTS.md).

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-purpose-scope-and-use-cases.md) | Purpose, scope and use cases (UC-1 to UC-15) | Accepted |
| [0003](0003-deployment-web-app-in-docker.md) | Deployment: a web app in Docker on a Linux server | Accepted |
| [0004](0004-pipeline-engine-reuses-discogs-scripts.md) | The pipeline engine is the unchanged discogs scripts | Superseded by 0036 |
| [0005](0005-technology-stack-and-conventions.md) | Technology stack and code conventions | Accepted (frontend parts superseded by 0029, Style bullet by 0034, one-file backend by 0036) |
| [0006](0006-status-model-and-pipeline-steps.md) | Status comes from FLAC tags; six pipeline steps | Accepted |
| [0007](0007-trust-boundary-and-secrets.md) | Trust boundary, no authentication, secrets | Accepted |
| [0008](0008-job-model.md) | Job model: one job at a time, queue, polling, write lock | Accepted |
| [0009](0009-settings-and-api-keys.md) | Settings and API keys | Accepted |
| [0010](0010-bliss-file-naming.md) | Bliss file naming after fixes and edits | Accepted (output folder layout: 0037) |
| [0011](0011-ingestion-move.md) | Moving fixed albums to the ingest folder | Accepted (flat target superseded by 0037) |
| [0012](0012-language-and-performance.md) | Stay in Python; speed up compute inside the discogs scripts | Superseded by 0036 |
| [0013](0013-discogs-track-assignment.md) | Discogs release search and track assignment | Accepted |
| [0014](0014-internal-tag-editor.md) | Internal tag editor; what is editable and what is Discogs-owned | Accepted |
| [0015](0015-track-playback-and-track-edit.md) | Track playback and per-track edit | Accepted |
| [0016](0016-cover-art.md) | Cover art: display, size warning, replacement | Accepted |
| [0017](0017-ui-layout-and-design-system.md) | UI layout and design system | Superseded by 0030 |
| [0018](0018-verification.md) | Verification without touching real data | Accepted |
| [0019](0019-version-control-and-releases.md) | Version control and releases | Superseded by 0020 |
| [0020](0020-work-directly-on-main.md) | Work directly on main; no feature branches | Accepted |
| [0021](0021-lrclib-lyrics-search.md) | Lyrics search on lrclib.net in the track editor | Accepted |
| [0022](0022-top-bar-instead-of-sidebar.md) | Top bar instead of a sidebar | Superseded by 0030 |
| [0023](0023-musicbrainz-release-search.md) | MusicBrainz release search and tags | Accepted |
| [0024](0024-delete-cover-removes-folder-image.md) | Delete cover also removes the folder image | Accepted |
| [0025](0025-fingerprint-length-in-discogs-repository.md) | Fingerprints read the first 120 seconds (discogs repository change) | Accepted |
| [0026](0026-ready-filter-returns.md) | The Ready filter returns to the top bar | Accepted |
| [0027](0027-legacy-dynamic-range-tags-removed.md) | Legacy spaced dynamic-range tags removed from the discogs scripts | Accepted |
| [0028](0028-replaygain-skip-needs-album-gain.md) | rsgain skips an album only when it already has album gain | Accepted |
| [0029](0029-nextjs-frontend-static-export.md) | Frontend in Next.js with shadcn/ui, built to a committed static export | Accepted |
| [0030](0030-ui-layout-and-design-system-v2.md) | UI layout and design system v2 (shadcn/ui; its sidebar replaced by 0031) | Accepted |
| [0031](0031-top-bar-again.md) | Top bar again, no sidebar, no Artists list | Accepted |
| [0032](0032-parallel-tag-writes-reopen-before-save.md) | Parallel pipeline scripts reopen a file before saving (discogs repository change) | Accepted |
| [0033](0033-pipeline-tag-steps-run-in-sequence.md) | Dynamic range, ReplayGain and fingerprints run in sequence (discogs repository change) | Accepted |
| [0034](0034-python-formatting-and-linting-with-ruff.md) | Python formatting and linting with ruff | Accepted |
| [0035](0035-automated-tests-with-pytest.md) | Automated tests with pytest on synthetic albums | Accepted |
| [0036](0036-standalone-pipeline-package.md) | A standalone pipeline package; the discogs repository is no longer needed | Accepted |
| [0037](0037-library-watcher-and-layout.md) | The library folder: layout template, watcher, status | Accepted |
| [0038](0038-staging-and-library-views.md) | Staging and Library views; one name for each folder | Accepted |
| [0039](0039-incomplete-and-what-is-missing.md) | "Incomplete" instead of "Ready", and showing what is missing | Accepted |
| [0040](0040-channel-badges.md) | Channel badges (Mono, Stereo, 5.1, 7.1) on tracks | Accepted |
| [0041](0041-wider-inspector.md) | A wider inspector on wide screens | Accepted |
| [0042](0042-covers-are-scaled-on-upload.md) | A dropped or fetched cover is scaled to the limit at once | Accepted |
| [0043](0043-assignment-refreshes-the-discogs-tags.md) | Assigning a Discogs release refreshes the Discogs-owned tags at once | Accepted |
| [0044](0044-lrclib-application-id-no-key-setting.md) | lrclib.net is reached with the application ID; no key setting | Accepted |
| [0045](0045-folders-from-the-environment-only.md) | Staging and library folders come from the environment only; Settings shows their host paths | Accepted |
| [0046](0046-discogs-medleys-are-one-release-track.md) | A Discogs medley (index entry with sub-tracks) is one release track | Accepted |
| [0047](0047-a-real-catalogue-number-replaces-none.md) | A real catalogue number replaces the placeholder `none` on assignment | Accepted |
| [0048](0048-reassignment-replaces-what-the-previous-release-filled.md) | Re-assigning replaces the release-level tags the previous release filled | Accepted |
| [0049](0049-tag-edits-refresh-the-version-at-once.md) | Editing format, catalog # or edition refreshes the Discogs tags (VERSION) at once | Accepted |
| [0050](0050-lyrics-are-optional.md) | Missing lyrics are an optional, blue notice; they do not block `fixed` or the move | Accepted |
| [0051](0051-run-a-single-pipeline-step.md) | A double click on a pipeline step runs only that step | Accepted |
| [0052](0052-discogs-search-by-attributes-and-musicbrainz-match.md) | The Discogs search starts with artist and album and marks MusicBrainz matches | Accepted |

## Which ADR covers what

| If you change... | Read first |
|------------------|-----------|
| what the app is for, a new feature | 0002 |
| Docker, environment variables, mounts | 0003 |
| Run fixes, the pipeline steps, `drcalc`, anything that used to be a discogs script | 0036, 0006 |
| backend dependencies | 0005 |
| Python formatting, linting, annotations, `pyproject.toml` | 0034 |
| tests, fixtures, the `test` dependency group | 0035, 0018 |
| the `pipeline/` package, API clients, Discogs tags, `drcalc` | 0036, 0014, 0013 |
| the output folder layout, the watcher, the Library tab, the status indicator, Move to library | 0037, 0010, 0011 |
| the Staging / Library switch, folder names, which folders the UI may read | 0038, 0007 |
| status names, the Missing box, the missing badges on cards | 0039, 0006 |
| track rows and the badges on them (channels) | 0040, 0015 |
| frontend stack, `ui/`, building `static/ui/` | 0029 |
| statuses, steps, lyrics rules, scan cache | 0006 |
| paths, endpoints, secrets, access | 0007 |
| jobs, queue, log, endpoints that write | 0008 |
| settings dialog, API keys, config overlay | 0009, 0044 (no lrclib key), 0045 (folders read-only) |
| file names, `rename_files`, `clean()` | 0010 |
| Move to ingest | 0011 |
| Discogs search, track assignment | 0013 |
| MusicBrainz search, MusicBrainz tags | 0023 |
| tag editor, override pencils, which tags are editable | 0014 |
| play button, track edit dialog, lyrics editing | 0015, 0021 (artist field, lrclib search) |
| cover display, size warning, cover upload | 0016 |
| cover delete | 0024 |
| fingerprint length | 0025 |
| parallel tag writes by pipeline scripts (lost tags), step order and concurrency in `nzbfix` | 0032, 0033 |
| dynamic-range tag names | 0005, 0027 |
| ReplayGain skip | 0028 |
| top bar navigation entries | 0031, 0026 |
| layout, colours, widths, dialogs, UI styling | 0030 (colours, cards, dialogs), 0031 (top bar) |
| how to test | 0018 |
| commits, pushing, tags (no branches) | 0020 |
