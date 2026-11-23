# Changelog

What changed for people who use Tagwright, newest first. Every functional change and bug fix gets an entry in the commit that makes it ([ADR 0069](docs/adr/0069-release-notes-and-commit-descriptions.md)); the entries below `Unreleased` become a version's notes when a release is tagged. The entries before this file existed were written afterwards from the commit history and are grouped by theme, not by commit; numbers in brackets are ADRs.

## Unreleased

### Fixed

- `scripts/fix-credits.py` no longer skips tracks as "no matching Discogs track" when the release numbers them differently (SACD-1, CD-1 against your 1, 2): it then matches by title, ignoring the parts in other scripts ("Travelin' Prayer = 流れ者の祈り" matches "Travelin’ Prayer") and the kind of apostrophe. Only a title that fits exactly one track counts [0100].

## 0.5.0 (2026-11-23)

### Changed

- Assigning a Discogs release writes artists and credits one name per value, as Roon reads them: ARTIST, COMPOSER, LYRICIST, ARRANGER, CONDUCTOR, REMIXER, MIXER, PRODUCER, ENGINEER, and PERSONNEL ("Name - Role", mastering included) for everything else. Credits Discogs limits to some tracks no longer land on every track. Old credit lists (PERFORMERYR, INVOLVEDPEOPLE…) and leftover tags from earlier taggers and rippers are removed. A track's artists show as "A; B" in the Tag Editor [0100].
- New script `scripts/fix-credits.py` brings existing albums up to the same rules from a fresh Discogs lookup (dry run by default, `--write` to save) [0100].

- Box sets can have their own cover: on a multi-disc album the first field under "All discs" is now Box Cover. It is stored in every file next to each disc's own cover (the disc cover comes first) and becomes folder.jpg in the box folder, as Roon expects; disc folders keep their own covers and fall back to the box cover [0099].
- Multi-disc albums show an "Artwork for" switch above the cover fields: pick a disc to see and change only that disc's front cover, back cover, leaflet and media images; "All discs" works as before [0098].
- Changing artwork on a library album now rewrites its cover files on disk (folder.jpg and Artwork/) to match, and removes files for images you deleted. Albums with disc folders get a set per disc folder, and folder.jpg in the album folder [0098].
- The Tag Editor's Album tab shows the album's current format in the Album Format field (it was empty unless an override was set). Type over it to change the format; no override tag is written, and an empty field means CD. Assigning a Discogs release still sets the release's format [0097].
- The card/list buttons sit in a pill, and together with Rescan they moved between the Staging / Library switch and the search [0095].
- Every text field now shows an x while it has text and you point at it or type in it; clicking it empties the field (number and read-only fields and the lyrics editor excepted). The search field no longer shows the ⌘K hint; ⌘K still jumps to it [0094].
- List view rows are shorter, so more albums fit on screen without scrolling [0087].

### Fixed

- An assignment that would empty a file's title, artist, album, album artist, track or disc number (for example from a broken Discogs answer) is no longer saved for that file; the log names it [0100].
- Remove cover works again; confirming the dialog showed "[object Object]" and left the cover in place [0090].
- Pasting an image (Cmd/Ctrl+V) now works in the Back Cover, Leaflet and Media fields too; click the field, then paste, and the image is added to that set [0096].
- MP3 files converted with ffmpeg (or tagged by tools that store track and disc totals, label, media or comment as extra text frames) no longer make the Discogs tags step fail with "disctotal"; those values are read and moved into the standard ID3 frames when the file is saved [0059].
- The Front Cover options menu now sits in the field's bottom-right action row instead of beside the title, leaving the header clearer [0090].
- Cover images now fill their field instead of being letterboxed, and each field shows the image's pixel size in its header (with the file size on hover) [0093].
- Cover previews now use the full square field, so large artwork no longer occupies only the upper half of its cover box [0093].
- The track list in the Discogs and MusicBrainz assignment dialogs now follows the release track's disc and track order, so a multi-disc release shows one subtitle divider per disc instead of repeating discs [0089].
- The full-bleed layout applies only to the list table; card view keeps its original padding around the cards [0087].
- The list's title row stays at its aligned position while scrolling instead of shifting; rows pass behind an opaque strip above it [0088].

### Added

- Embedded artwork is now editable by type in the inspector: the album details use the full width, with four equal cover fields below them — **Front Cover** (one image), **Back Cover**, **Leaflet** and **Media** (several images each, with arrows to cycle). Drop or paste replaces the selected image, Delete removes it and + adds another; double-click an image to see it full size (click or Escape closes). Moving an album to the library recreates `folder.jpg` and numbered files under `Artwork/` from the embedded images, so a music server that cannot read embedded art still gets covers [0090, 0091].

- A **view switch** in the top bar, next to Rescan: two buttons, **cards** and **list**, with the active one pressed. The list is a compact, full-width **data table** with a sticky title row, high-contrast alternating rows and columns for album artist, release name, media, edition, catalog number, dynamic range, release year (**Release**) and master year (**Master**). DR values of 12 and above are green, lower ones amber. Click any column heading to sort by it (again for descending), drag the edge of a heading to resize a column, and click a row to open the same inspector as a card. Column widths and the chosen view are remembered in the browser; no covers are shown in the list [0087].

## 0.4.0 (2026-11-18)

### Added

- An **"In your library"** box under the folder lines lists the other versions of the album's Discogs master that are already in the library, one line each with the album title and version. It needs the album to have a Discogs release; the first start after the update re-reads the library summaries once in the background [0082].

- The cover menu has **Paste image**: it takes an image from the clipboard and replaces the cover like a drop does. Over plain http on the LAN it asks you to press Cmd/Ctrl+V while the cover is focused [0056].

- The Tag Editor's Tracks tab shows the same read-only columns as the track list: time, sample rate and bit depth, and the lyrics badge, next to the channels [0014].

- The Discogs and MusicBrainz dialogs show the release's subtitles as dividers between the tracks, the same as the Tag Editor: Discogs headings (also inside a disc) and MusicBrainz disc titles. Each divider has a "Release" / "Keep mine" choice, the old subtitles of the files, a pen to type your own and "+ divider here"; "Import song titles" moved to the top right of the dialog [0081].

- The Tag Editor's Tracks tab shows the disc subtitles as dividers between the tracks instead of a column: a band per disc on albums with several discs (with a pen to set the subtitle), and a band wherever the subtitle changes inside a disc. "+ divider here" between two tracks adds a subtitle, the x removes one, and a track dragged across a divider takes that subtitle [0081].

- The track list shows each track's sample rate and bit depth (`44.1/16`, `192/24`; an MP3 shows the rate alone), and its lyrics badge is shorter: `LRC`, `TXT`, `INS` for instrumental and `---` for none, with the full text as hover text [0015].

- The MusicBrainz dialog assigns the album's files to the release's tracks, like the Discogs dialog, and renumbers and renames them [0078].
- With "Import song titles" on, the Discogs and MusicBrainz dialogs show an editable title for every file (so you can correct it during the import) and the old title below it with a copy button; what will not change is shown in light grey [0078].
- An **"Import song titles"** checkbox in the Discogs and MusicBrainz dialogs: off imports only the album data (release IDs, catalogue number, year and country) and keeps the files' titles, track and disc numbers and disc subtitles; on also writes the release's title, track number, disc number and disc subtitle (the heading before a disc on Discogs, the disc title on MusicBrainz), which the dialog shows [0078]. It is remembered; default on for Discogs, off for MusicBrainz [0078].

### Changed

- All notes in the inspector (problems, warnings, Missing, Optional, mismatches, hints) look the same: the type at the left, the text beside it, a button at the right; a red problem gets a stop symbol, a warning or hint a warning sign. **Missing** has a **Run fixes** button, a note about MusicBrainz has a **MusicBrainz** button, and **New folder** shows the album title with its version under the path, like the library versions [0083].
- A **year mismatch** between the Discogs and the MusicBrainz release is now a red **Mismatch** and stops **Move to library** until the release is fixed; there is no way to accept it [0083, 0023].

- Current folder, New folder and In your library are rows of one light grey box, the label at the left of its value (no separate headings), in the same style as the Missing and Optional boxes; further versions in the library are indented under the first [0082].

- The Missing and Optional boxes take one line per item ("MISSING  No fingerprints on all 9 tracks") and no longer list track names; the track list shows which tracks [0054, 0039].

- The cover's size and its "…" menu are one button at the left end of the action row, as wide as the cover and beside Tag Editor, Run fixes and Move to library, instead of a pill and a button under the cover [0056].

- A very long song title no longer makes the rename fail: the file name is cut so that it stays within 255 bytes. Shorter names are unchanged [0010].

- Discogs now leads the catalogue number, album format and credits (composer, producer, engineer ...): assigning a release writes them. A manual value is kept with the new Album Format Override and Catalog # Override fields in the Tag Editor. With "Import song titles" on, the track artist is written together with the title, in the Discogs and the MusicBrainz dialog [0080].

- The album artist now comes from Discogs: assigning a release and Run fixes both write it, replacing a different spelling in the files (for example "Simon and Garfunkel" becomes "Simon & Garfunkel"), so the library groups an artist's albums in one folder. An Album Artist Override is kept [0079].

### Fixed

- Dialogs no longer grow wider than the window when they hold long text, such as the file path above the lyrics editor: the content now stays inside the dialog.

- The Discogs and MusicBrainz track assignment dialogs no longer grow wider than the window when a file name is long: the release track and match columns stay inside the dialog.

- In the Discogs and MusicBrainz track assignment, the channel badge no longer touches the disc number field and the match pill no longer touches the scroll bar.

- With "Import song titles" off, the Discogs and MusicBrainz assignments now fill an empty disc number, track number or title from the release (a raw download has no disc number, so the album could not be named). Numbers and titles the files already have are still left alone [0078].

- A dialog no longer keeps showing "a job is running" after the job has finished.

## 0.3.0 (2026-11-13)

Everything since 0.2 (8 to 13 November 2026).

### Added

- **Maximum cover size** in Settings (default 1500 px), next to the minimum: covers larger than this are scaled down when uploaded or fetched and by Run fixes. It cannot be set below the minimum [0074].
- **Delete the leftover folder after a move**: a setting (off by default) makes Tagwright open a dialog after a successful "Move to library" that lists everything still in the album's folder of the staging folder, with sizes, and deletes the folder only when you press Delete [0072].
- A **copy button next to the catalogue number** in the inspector header, below the album art, copies just the number (not shown when the catalogue number is `none`).
- **Library**: a watcher keeps the library folder in the canonical artist/album/disc/file layout, waiting for files to settle before it moves anything. The layout is set in Settings by dragging tags into rows, with a live preview on a real album; a status indicator in the top bar shows artists, albums, tracks and activity, with a Re-analyze button [0037].
- **Staging | Library switch** in the top bar flips the board between the staging folder and the library, so details of albums already in the library can be fixed [0038]. Albums are listed from stored summaries and the watcher's index, so switching takes a fraction of a second instead of minutes on a network share [0067].
- **Move to library** shows exactly what will happen first: the album folder and every file name. Only fixed albums move and nothing is overwritten [0011, 0037].
- **MP3 support**: MP3 files are tagged, named, moved and analysed like FLAC, in the same album or in mixed albums. Tags are written as ID3v2.4 [0058, 0059].
- **Pipeline runs inside Tagwright**: dynamic range (`drcalc`), ReplayGain, fingerprints, Discogs tags and lyrics no longer need the separate discogs repository [0036]. Double-clicking a step in the pipeline bar runs just that step; the audio steps also run on albums that still need input [0051]. The bar shows an icon per step with check and warning badges, joined by a line, and the running step spins [0030].
- **MusicBrainz**: choose a release (search, using the album's Discogs release to find the same one) and write its ID, release group, album artist and artist links, plus barcode, ASIN, country, status and type where empty. Notes appear when the release disagrees with the Discogs one [0023]. The search starts with artist and album, shows them with copy icons, and marks results that link the album's Discogs ID [0023].
- **Discogs**: the dialog starts with artist and album, shows them with copy icons, and marks releases linked from the album's MusicBrainz release [0053]. A medley is one release track and its parts are tracks of their own, so files split by part can be assigned [0053, 0060]. Assigning a release fills what the old tagger imported and refreshes the Discogs-owned tags at once; assigning another release replaces what the previous one filled, and a real catalogue number replaces `none` [0053].
- **Tag editor** has five tabs: Album, Tracks, Discogs, MusicBrainz and a new Other tab listing every remaining tag [0057]. Tracks gain shift-select, bulk edit, renumber and drag-and-drop reordering [0014]. Changing format, catalog # or edition refreshes the version string at once and the step circles spin meanwhile [0054].
- **What is missing, at a glance**: "Incomplete" albums name what is open on the card and in the inspector, with the tracks affected; missing lyrics are an optional blue notice that no longer blocks Fixed or the move [0054]. A missing Discogs or MusicBrainz ID is a link that opens that site's search for the artist and title [0054].
- **Covers**: the size is shown under the cover, the pencil uploads a replacement, and a cover below the minimum size (a setting, 1400 px by default) turns the Tags and cover step yellow and keeps the album from moving, while Run fixes still works [0016]. A size pill and one actions menu (upload, search covers, remove) under the cover; a cover below the minimum size gets an amber outline and pill [0056]. Uploaded and fetched covers are scaled to 1500 px at once [0042]. Deleting a cover also removes the folder image [0024].
- **Track lists** show Mono, Stereo, 5.1 and 7.1 badges [0040]; the inspector header shows the release country's flag, the version string and the media type [0054]; copy buttons sit next to artist, album and the album facts.
- **Playback**: a Stop button in the top bar whenever a track plays, and playback stops by itself when its album leaves the list, for example after the watcher moved it [0068].
- **Logging**: the program's own lines (jobs, steps, moves, renames, assignments, tag, lyrics and cover edits, settings) go to standard output; `SYSLOG_HOST`, `SYSLOG_PORT` and `SYSLOG_PROTOCOL` add syslog, and `LOG_LEVEL` sets the detail. Successful status polls are left out of the access log [0064, 0065, 0066].
- **Published Docker image** for amd64 and arm64 on `ghcr.io/koehntopp/tagwright`, rebuilt weekly [0063]. The project is licensed GPL-3.0-or-later, with a NOTICE for third-party software [0062]. Renovate keeps dependencies current [0061].
- Lyrics: Instrumental and Spoken Intro buttons, lrclib.net search under another title or artist, and the application ID that gives Tagwright a higher rate limit [0015, 0021, 0044]. Cards and dialogs got spinners with what is running, and busy states reset when a dialog opens [0030].

### Changed

- The Run fixes button turns red and says "Running…" while the album is being fixed, like the other buttons that start work [0030].
- Applying a Discogs or MusicBrainz release: the dialog's button turns red and says "Applying…" while the tags are written, like the Move and Delete buttons [0053, 0023].
- Dropping or uploading a cover now shows progress: a spinner over the cover, "Processing…" in the size pill and a spinning Tags and cover step, until the cover is scaled and embedded [0056].
- The Move dialog's button turns red and says "Moving…" while the album is being moved, like the Delete dialog's button does.
- In the staging folder every top-level folder is now one album, whatever its subfolders are called: a box set with folders like "Disc 1 - Nebraska Outtakes" is one album, not four. Dynamic range is calculated over the whole album [0076].
- Fingerprints are now calculated by `fpscan` (the owner's Rust tool) instead of `fpcalc`: one run per album, FLAC and MP3, and no failures because of stray bytes after the last frame. New fingerprints differ slightly from `fpcalc`'s but match the same on AcoustID; existing ones are kept [0075].
- **New interface** on Next.js and shadcn/ui, with a top bar instead of the sidebar; the pipeline status moved there too. The inspector grows to 720 px on wide screens [0029, 0030, 0031, 0041].
- **Settings**: the staging and library folders are no longer editable; they come from `STAGING_FOLDER` and `LIBRARY_FOLDER` and Settings shows their host paths. There are no default paths: `STAGING_FOLDER`, `LIBRARY_FOLDER` and `DATA_DIR` must be set, and the compose file takes the host paths from a `.env` file [0045, 0055]. The lrclib.net key setting is gone [0044].
- "Ready" is now called "Incomplete", and without a Discogs release ID the red Discogs line is the only line shown [0054].
- The Discogs and MusicBrainz tabs, album lists, search results and the Move dialog were reworked for width, alignment and consistent badge columns [0030, 0031].
- Python 3.14; the code is formatted and linted with ruff [0034]; automated tests (pytest) cover status, naming, jobs, moves, the pipeline steps, the library, logging and MP3 [0035].
- Folders named `CD N` are grouped like `Disc N`; hidden folders and files are ignored; the staging folder itself is never an album [0006, 0054].

### Fixed

- Switching between staging and library kept the search text, so the other folder showed an empty board although its counts were not zero. The search is cleared on a switch, and an empty result names the search text.
- The "Delete the folder?" dialog said the folder "holds nothing" when it held only empty subfolders (CD 1, CD 2). It now counts and lists the subfolders and says that they are deleted too [0072].
- The Move to library dialog said that images and logs "stay in the staging folder" even when Settings offers to delete the folder afterwards. It now says that you will be asked whether to delete what is left [0072].
- A track got no fingerprint when its FLAC had stray bytes after the last frame (for example an ID3v1 block), because the newer decoder in the Docker image made `fpcalc` exit with an error even though it had printed the fingerprint. The fingerprint is now used and a warning names the file [0073].
- The Discogs search link behind a missing Discogs ID opened a results page without Discogs' header. It now opens the general Discogs search (all result types, in the address `discogs.com/search?type=all&q=…`), which shows the page normally [0054].
- A run that was going when the server restarted (for example a redeploy) left the page showing it as running for ever. The page now keeps asking while the server is away, and when it is back it clears the run and says it was interrupted.
- An album that cannot be read (for example after a network error) no longer breaks the whole board; its card says what failed.
- After the watcher moved an album (a corrected artist name), the board kept an old card with no files. It now reloads when the library changes and drops cards whose folder is gone [0067].
- Playback could not be stopped once its album had moved [0068].
- Copy buttons did nothing over plain http; they now work.
- The lyrics and album editors lost what was typed when the page refreshed in the background.
- The MusicBrainz year note compared with the year tags in the files instead of the Discogs release's own year [0023]; a corrected Discogs release left the note in place.
- A cover deleted from the folder kept showing from the browser cache; the album list showed stale state after edits; a rebuilt page was served stale.
- Empty tags are never replaced by "Unknown" in file and folder names, and title, track number, disc number and catalog number must not be empty [0006, 0010].
- Many smaller fixes to widths, spacing, alignment and wording in the top bar, cards, dialogs and the track list.

### Removed

- The separate discogs repository as a dependency, the external tagger link, the "Run all ready" button and the sidebar [0036, 0014, 0031].

### Security

- API keys are never logged or returned; the Discogs key is the only one left, kept in `settings.json` [0007, 0044].
- The repository was cleaned of private addresses and the old commit email, secret scanning and push protection are enabled, and the UI's dependency audit is clean for the code that ships.

## 0.2 (8 November 2026)

- Internal tag editor replaces the link to an external tagger: album fields the pipeline never overwrites, per-track title, artist and numbers, and the tags written by Discogs shown read-only [0014].
- Assign an album's files to a Discogs release, renumbering them and filling artist, album artist, album, catalog number and cover where missing [0013].
- Track list: play and pause, edit lyrics, track length, editable disc and track numbers in the Discogs window.
- Wider inspector and album artist and title overrides.
- The app is renamed from Album Fixer to Tagwright.

## 0.1 (8 November 2026)

- First version, "Album Fixer": a board of album cards from the input folder with cover, artist, album, year, Discogs and MusicBrainz IDs, album DR and lyrics counts; Run fixes with a live log; moving fixed albums to the ingest folder; Settings for the folders and API keys [0002].
