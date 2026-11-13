# Tagwright

A self-hosted web app that turns freshly downloaded FLAC and MP3 albums into clean, tagged, loudness-analysed albums with lyrics, and keeps your music library in one canonical folder layout.

One user, one browser tab. FastAPI backend, Next.js frontend, no database server, no account. The decisions behind every behaviour are in [docs/adr/](docs/adr/README.md).

![The board: one card per album, the inspector on the right](docs/screenshots/board.png)

## What it does

You point Tagwright at two folders: a **staging folder** (where downloads land) and a **library folder** (what your music server reads). It then helps you take an album from one to the other.

1. **See what each album needs.** Every album in the staging folder is a card with cover, artist, album, year, Discogs ID, dynamic range, lyrics and a pipeline progress bar. The top bar filters: *Needs input*, *Incomplete*, *Fixed*.
2. **Fix it.** *Run fixes* runs the pipeline on the album and streams a live log.
3. **Correct what automation cannot.** Choose the Discogs and MusicBrainz release, edit tags, fix lyrics, replace the cover.
4. **Move it to the library.** *Move to library* places the files in the library layout.

### Card colours

| Colour | Meaning |
|---|---|
| Green, *Fixed* | Every pipeline step is done |
| Blue, *Incomplete* | Has a Discogs release, some steps are missing; the card lists which |
| Red, *Needs input* | No Discogs release yet. This is the only warning shown until one is assigned |

## The pipeline

One run does these steps in this order (ADR 0036):

1. **Dynamic range** with [`drcalc`](https://github.com/koehntopp/drcalc) (`DYNAMIC_RANGE`, `ALBUM_DR`)
2. **ReplayGain** with `rsgain`
3. **Fingerprints** with [`fpscan`](https://github.com/koehntopp/fpscan) (AcoustID)
4. **Tags & cover** from the assigned Discogs release
5. **Lyrics** from [lrclib.net](https://lrclib.net), synced (LRC) when available
6. **Filenames** in the layout's file name pattern

The inspector shows each step as done or partial, and which tracks lack it.

![Inspector: pipeline steps, track list with channel and DR badges](docs/screenshots/inspector.png)

Tags Tagwright writes are never read back as input, tags owned by Discogs are read-only in the editor, and a user-owned tag is never overwritten by automation (ADR 0004, 0014).

## Editing

**Tag editor** has four tabs: Album, Tracks, Discogs and MusicBrainz. Tracks lets you change disc, track number, title, artist and disc subtitle, reorder by drag and drop, and see whether a track is Stereo, Mono, 5.1 or 7.1.

![Tag editor, Tracks tab](docs/screenshots/tag-editor-tracks.png)

**Discogs** search assigns an album's files to the tracks of a release, which matters when the download holds only a subset of the release. The Discogs-owned tags (album name, version, catalog number, year, ...) are written at once. **MusicBrainz** search picks the matching release and stores its IDs and links, and warns when its year differs from the Discogs release.

**Lyrics** are edited per track, optionally after searching lrclib.net under another title or artist.

![Lyrics editor](docs/screenshots/lyrics-editor.png)

**Cover**: the pixel size is shown and a small cover is flagged. Drop an image on the cover or use the upload button; it is scaled to 1500 px and embedded. Links open cover searches on external sites.

## Moving to the library

*Move to library* shows exactly what will happen first: the album folder and every file name, from your layout. Only `fixed` albums can move, nothing is overwritten and nothing is merged into an existing folder (ADR 0011).

![Move dialog with preview](docs/screenshots/move.png)

## The library watcher

A background watcher keeps the library folder in the layout. It notices changes without re-listing the whole share (it compares directory modification times), waits for a cooldown after the last change, and only then renames and moves. It never overwrites, removes only empty folders and obvious litter.

The top bar shows album artists, albums and tracks, and what the watcher is doing. Click it for recent activity and a manual **Re-analyze** button.

![Library status dialog](docs/screenshots/library-status.png)

The **Staging | Library** switch in the top bar flips the board to the library, so you can fix details of albums that are already there.

![The board showing the library](docs/screenshots/library.png)

### The layout

Settings, tab *Library*, defines the layout by dragging tags into rows: one row per folder level, one for the disc folder of multi-disc albums, one for the file name. A live preview uses a real album. *Reset to bliss default* restores `Artist/Album_Year_DRxx_Format_Catalog/01_01_Title.flac`.

![Layout editor](docs/screenshots/settings-layout.png)

## Run it

Requirements: Python 3.14, [`uv`](https://docs.astral.sh/uv/), and on `PATH`: `drcalc`, `rsgain`, `fpscan`.

```bash
STAGING_FOLDER=/path/to/staging LIBRARY_FOLDER=/path/to/library DATA_DIR=./data ./app.py
```

Open <http://localhost:8080>. In Settings enter your **Discogs API key** (required for the Discogs step). It lives in `DATA_DIR/settings.json` and is never logged or returned by the API. lrclib.net needs no key: Tagwright identifies itself with its registered application ID.

| Variable | Meaning |
|---|---|
| `STAGING_FOLDER` | Staging folder (required) |
| `LIBRARY_FOLDER` | Library folder (required) |
| `DATA_DIR` | Settings, library index, MusicBrainz cache (required) |
| `PORT` | HTTP port (optional, 8080) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR` (optional, `INFO`); `DEBUG` adds per-file detail |
| `SYSLOG_HOST` | Also send the log to this syslog host (optional) |
| `SYSLOG_PORT` | Syslog port (optional, 514) |
| `SYSLOG_PROTOCOL` | `udp` (default) or `tcp` (optional) |

There are no default paths: Tagwright refuses to start when one of the three is missing. Paths must be absolute. Staging, library and every path the API accepts are checked against these two folders. They are not editable in Settings, which shows them read-only, as host paths (the bind-mounted path or the NFS export) when it can tell.

### Logging

The program logs jobs, moves, renames, assignments, tag, lyrics and cover edits and settings saves to standard output (`docker logs`). Set `SYSLOG_HOST` to send the same lines to a syslog server too (not needed when Docker's syslog log driver already ships the container output). Successful status polls of the page are left out of the access log. API keys are never logged ([ADR 0064](docs/adr/0064-logging-and-syslog.md)).

### Docker

A published image (amd64 and arm64) is on GitHub's registry; each release also has its own tag (for example `:0.3`, [ADR 0070](docs/adr/0070-releases.md)):

```bash
docker pull ghcr.io/koehntopp/tagwright:latest
```

Or build and run it with compose:

```bash
docker compose up -d
```

Set `STAGING_HOST_PATH` and `LIBRARY_HOST_PATH` in a `.env` file next to [compose.yaml](compose.yaml); it mounts them at `/staging` and `/library`, and `./data` at `/data`. The image contains Python, `drcalc`, a source-built `rsgain` and `fpscan`.

Tagwright has no authentication. Run it on a trusted network or behind a reverse proxy that authenticates (ADR 0007).

## Development

```bash
uv run --group test pytest            # tests use synthetic albums in a temp directory
uv run ruff check . && uv run ruff format --check .
cd ui && npm run build                # frontend; commit the resulting static/ui/
```

Layout: `app.py` (web layer), `pipeline/` (the steps), `library/` (watcher, planner, layout template), `ui/` (Next.js, shadcn/ui), `docs/adr/` (the specification).

Never run tests or experiments against a real library (ADR 0018). Contributors and AI agents: read [AGENTS.md](AGENTS.md) first; the ADRs are binding.

## Licence

Tagwright is free software under the [GNU General Public License, version 3 or later](LICENSE). It builds on `mutagen` and `Unidecode`, which are GPL, so the combined program and the Docker image are GPL ([ADR 0062](docs/adr/0062-license-gpl-3-or-later.md)). [NOTICE](NOTICE) lists the third-party software it uses and the image contains.
