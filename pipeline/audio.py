"""Audio files: the one seam between Tagwright and the tag library (ADR 0058).

Everything else opens files with `open_audio` and works on the `Audio` interface: mutagen's FLAC interface (a
case-insensitive dict of lists in `.tags`, `.pictures`, `add_picture`, `clear_pictures`, `.info`, `save`). Today the
only implementation is FLAC itself; another format has to provide the same surface.
"""

from pathlib import Path

from mutagen.flac import FLAC, Picture

type Audio = FLAC
type Cover = Picture

EXTENSIONS = ('.flac',)


def is_audio(name: str) -> bool:
	"""True for a file name this program handles (by extension, any case)."""
	return name.lower().endswith(EXTENSIONS)


def open_audio(path: Path | str) -> Audio:
	"""Open an audio file for reading and tagging; mutagen's own errors are raised for a damaged file."""
	return FLAC(path)


def new_cover() -> Cover:
	"""An empty picture to fill in before `add_picture`."""
	return Picture()
