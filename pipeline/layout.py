"""Album folders (ADR 0054, 0076).

In the staging folder every folder directly below it is one album, with all audio below it, whatever its
subfolders are called (`Disc 1 - Outtakes`, `CD2`, `Bonus`). Elsewhere (the library: `Artist/Album/Disc N`) a
`Disc N` / `CD N` folder belongs to its parent album, the rule of `DISC_DIR_RE` in the discogs `disc_layout.py`
this replaces, so existing libraries group exactly as before. The base folder itself is never an album.
"""

import os
import re
from pathlib import Path

from pipeline.audio import is_audio

DISC_DIR_RE = re.compile(r'^(?:Disc|CD)\s*(\d+)$', re.IGNORECASE)

STAGING: Path | None = None  # the staging folder; set by the web layer at start-up


def is_disc_dir(name: str) -> bool:
	"""True for a disc subfolder name (`Disc 2`, `CD1`, `disc 2`)."""
	return DISC_DIR_RE.match(name) is not None


def album_root(path: Path) -> Path:
	"""The album directory of a directory: the parent of a `Disc N` folder, else itself."""
	return path.parent if is_disc_dir(path.name) else path


def find_flacs(base: Path) -> list[Path]:
	"""All FLAC files below base, sorted. Hidden folders and files (a name starting with a dot: `.slskd-incomplete`
	downloads in progress, AppleDouble `._x.flac`) are skipped without being entered."""
	found = []
	for root, dirs, files in os.walk(base):
		dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
		found += [Path(root) / f for f in files if is_audio(f) and not f.startswith('.')]
	return sorted(found)


def flacs(album: Path) -> list[Path]:
	"""The FLAC files of an album, sorted: those in its own folder and those in its `Disc N` / `CD N` folders. Other
	subfolders are other albums (or art) and not part of this one."""
	if STAGING is not None and album.parent == STAGING:
		return find_flacs(
			album
		)  # the top-level folder is the album, whatever is below it (ADR 0076)
	found = []
	try:
		entries = sorted(os.scandir(album), key=lambda e: e.name)
	except OSError:
		return []
	for e in entries:
		if e.name.startswith('.'):
			continue
		if e.is_file(follow_symlinks=False) and is_audio(e.name):
			found.append(Path(e.path))
		elif e.is_dir(follow_symlinks=False) and is_disc_dir(e.name):
			found += find_flacs(Path(e.path))
	return sorted(found)


def album_dirs(base: Path) -> list[Path]:
	"""The albums below base: in the staging folder its top-level folders, elsewhere every folder with FLACs, a
	`Disc N` folder counting as part of its parent. The base folder itself is never an album (ADR 0006): a `CD1`
	folder lying directly in it is an album of its own."""
	if STAGING is not None and base == STAGING:
		return sorted(
			d for d in base.iterdir() if d.is_dir() and not d.name.startswith('.') and find_flacs(d)
		)
	found = set()
	for f in find_flacs(base):
		d = f.parent
		found.add(d.parent if is_disc_dir(d.name) and d.parent != base else d)
	return sorted(found)
