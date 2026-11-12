# ADR 0059: MP3 support

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

The owner's library and downloads contain MP3 files next to FLAC. The pipeline tools already handle MP3: `drcalc`, `rsgain` and `fpcalc` read it, and the first two write their results as ID3 `TXXX` frames named like the Vorbis keys (`DYNAMIC_RANGE`, `ALBUM_DR`, `REPLAYGAIN_*`). What was FLAC-only was Tagwright's own tag access ([0058](0058-audio-files-through-one-seam.md)).

## Decision

- **Formats**: FLAC and MP3. M4A, Ogg and the rest are out of scope. An album may **mix** formats; every file is read, tagged and named by its own format, and an album's status looks at all of them.
- **One tag model**: the program keeps thinking in Vorbis-style tags (upper-case keys, lists of strings). `pipeline/mp3.py` (`Mp3Audio`) gives an MP3 file the same surface as a FLAC file ([0058](0058-audio-files-through-one-seam.md)) by mapping keys to ID3 frames:
  - the usual fields (title, artist, album artist, album, date, genre, composer, label, media, disc subtitle, sort names, ...) are their text frames, `DATE` is `TDRC` and `ORIGINALDATE` is `TDOR`;
  - `TRACKNUMBER`, `TRACKTOTAL` and `TOTALTRACKS` are the two halves of `TRCK` ("3/12"); `DISCNUMBER`, `DISCTOTAL` and `TOTALDISCS` of `TPOS`;
  - `LYRICS` is the `USLT` frame, `COMMENT` the `COMM` frame;
  - every other key is a `TXXX` frame whose description is the key, in any case when reading. This covers the Discogs and MusicBrainz tags, `DYNAMIC_RANGE`, `REPLAYGAIN_*`, `ACOUSTID_FINGERPRINT`, `VERSION`, the overrides and the `ALBUM_*` families. MusicBrainz IDs are `TXXX:MUSICBRAINZ_ALBUMID` and so on, not the spellings other taggers use, but a description such as `MusicBrainz Album Id` is read as the key `MUSICBRAINZ ALBUM ID`.
  - Covers are `APIC` frames (front cover = type 3); their pixel size is measured when read.
  - Frames with no key (ratings, play counts, private frames) are left alone and not shown.
- **ID3 version: v2.4 is written, v2.3 and v2.4 are read.** v2.3 was the first choice for player compatibility, but it cannot hold several values in one frame: they would have to be joined with a separator that also occurs in the values (a `/` splits `DISCOGS_VIDEO_URL`, a genre such as "R&B/Soul"). Many tags here are multi-valued (genre, label, composer, credits, URLs). v2.4 stores them natively, in UTF-8. A file keeps an ID3v1 block if it had one.
- **Steps**: all six apply to MP3, including **dynamic range** (kept on request; the DR value of a lossy file is that of the decoded stream). `Lyrics` are written as unsynchronised lyrics (USLT) holding the LRC text.
- **File names**: a file keeps its own extension (lower case) when renamed or moved: the Filenames step, the rename after edits and the library planner use the file's suffix. A target name is `<stem><suffix>`.
- The player endpoint answers `audio/mpeg` for MP3.

## Consequences

- The tag editor's **Other** tab shows the mapped keys of an MP3 file, not raw frame names; unmapped frames are invisible.
- `fixtags` writes keys with spaces (`ORIGINAL DATE`, `ORIGINAL YEAR`) as `TXXX` descriptions, which ID3 allows.
- Not verified by the tests: how a given player or Roon treats these custom frames; only the files written on a copy are checked.
