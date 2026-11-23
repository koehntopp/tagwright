# ADR 0109: The proposal keeps each album disc in one release section and matches medley parts by their full title

- **Status**: Accepted
- **Date**: 2026-11-23
- **Supersedes in part**: [0053](0053-discogs-search-and-assignment-consolidated.md) (the proposal's scoring), [0060](0060-parts-of-a-work-are-release-tracks.md) ("the proposal fills whole tracks first; the parts then take only the files that are left"), [0102](0102-one-release-track-on-several-discs.md) (when every album disc is numbered on its own)

## Context

The Alan Parsons Project, *Tales Of Mystery And Imagination* (Blu-ray, Discogs 9448188) lists two mixes on one release disc, under two headings: the 5.1 mix with Orson Welles (tracks 1-7) and the original 1976 stereo mix (8-14), each with *The Fall Of The House Of Usher* as a medley in five parts. The album has a disc per mix (Disc 1 stereo, Disc 2 5.1, both numbered 1-11, the medley as five files titled "The Fall Of The House Of Usher (Prelude)" etc.). The proposal

- put three files into the other mix: the "same disc and track number" bonus pointed disc 1, track 5 at the 5.1 block's track 5;
- gave the part files the whole medley (whole tracks are matched first, and a part's own title "Prelude" looks nothing like the file's title), leaving six files on Skip;
- and, the rows being in release order (0089), showed the album's tracks scrambled. Its default numbering would also have put all 22 files on disc 1 as tracks 1-22.

## Decision

- **Scoring**: a part of a medley is compared both by its own title and as "medley part" ("The Fall Of The House Of Usher Prelude"); the better counts. For a title the release lists more than once, the "same disc and track" bonus is not given (the subtitle bonus of 0102 decides between the copies); other tracks keep it.
- **One pass for whole tracks and parts**: whole tracks from 0.35 and parts from 0.45 are taken in the same greedy pass from the best score, then the reuse pass of 0102. A file of a part now takes the part; a file of the whole medley still takes the whole entry, which scores better on title and duration.
- **Album discs stay together**: when the release has more than one section (a section is a run of the same release disc and subtitle), the proposal runs twice. After the first run, the section that more than half of an album disc's assigned files landed in becomes that disc's home; the second run adds 0.2 to every pair of a file with a track of its disc's home section.
- **Every album disc on its own** (listing order 0089 and default numbering 0053/0102): when a release track goes to several album discs (0102), *or* the album's discs that have assigned files are more than the release discs those tracks are on, the rows are listed by album disc, then release disc, track and index, and each album disc is numbered 1..n on its own. Otherwise listing and numbering stay as before. The dialog and the server use the same rule (`per_album_disc`).
- The macOS port follows, except for the medley parts, which it does not list as release tracks yet (see its GAPS).

## Consequences

- The example is proposed completely: Disc 1 to the stereo mix (8-14 with the five parts of 13), Disc 2 to the 5.1 mix (1-7 with the parts of 6), listed and numbered Disc 1 1-11, Disc 2 1-11.
- On a normal multi-disc album the home section of each album disc is its release disc, so the second run only reinforces the first.
- Import song titles writes a part's own title ("Prelude"), as before; the editable title field keeps the file's title when wanted. (Changed by [0110](0110-medley-parts-import-with-the-medley-title.md): parts are imported as "Medley (Part)".)
