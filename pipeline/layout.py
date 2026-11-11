"""Album folders: a `Disc N` / `CD N` folder belongs to its parent album (ADR 0006).

The same rule as `DISC_DIR_RE` in the discogs `disc_layout.py` this replaces, so existing libraries
group exactly as before. `ROOT` itself is never an album.
"""

import re
from pathlib import Path

DISC_DIR_RE = re.compile(r'^(?:Disc|CD)\s*(\d+)$', re.IGNORECASE)


def is_disc_dir(name: str) -> bool:
	"""True for a disc subfolder name (`Disc 2`, `CD1`, `disc 2`)."""
	return DISC_DIR_RE.match(name) is not None


def album_root(path: Path) -> Path:
	"""The album directory of a directory: the parent of a `Disc N` folder, else itself."""
	return path.parent if is_disc_dir(path.name) else path


def flacs(album: Path) -> list[Path]:
	"""All FLAC files of an album, sorted (its own files and those in disc folders)."""
	return sorted(album.rglob('*.flac'))


def album_dirs(base: Path) -> list[Path]:
	"""The albums below base: every folder with FLACs, a `Disc N` folder counting as part of its parent."""
	found = set()
	for f in base.rglob('*.flac'):
		d = f.parent
		found.add(d.parent if is_disc_dir(d.name) else d)
	return sorted(found)
