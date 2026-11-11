"""Small FLAC helpers shared by the steps."""

import logging
import os
from pathlib import Path

from mutagen.flac import FLAC

log = logging.getLogger(__name__)


def upper_tags(audio: FLAC) -> dict[str, list[str]]:
	"""All tags of a file with upper-cased keys and string values (empty without a Vorbis comment)."""
	return {k.upper(): [str(x) for x in v] for k, v in audio.tags.items()} if audio.tags else {}


def touch(path: Path) -> None:
	"""Update the mtime after a save, so caches and sync tools notice the change."""
	try:
		os.utime(path, None)
	except OSError as e:
		log.warning('Could not touch file mtime for %s: %s', path, e)
