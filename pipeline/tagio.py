"""Small FLAC helpers shared by the steps."""

import logging
import os
import re
from collections.abc import Mapping
from pathlib import Path

from mutagen.flac import FLAC

log = logging.getLogger(__name__)

type Tags = Mapping[
	str, list[str]
]  # what mutagen gives for a FLAC file (an empty dict without tags)


def tag(t: Tags, *keys: str) -> str:
	"""The first non-empty value of the keys, in order ('' if none)."""
	for k in keys:
		v = t.get(k)
		if v:
			return v[0]
	return ''


def upper_tags(audio: FLAC) -> dict[str, list[str]]:
	"""All tags of a file with upper-cased keys and string values (empty without a Vorbis comment)."""
	return {k.upper(): [str(x) for x in v] for k, v in audio.tags.items()} if audio.tags else {}


CHANNEL_HINTS = (
	(re.compile(r'(?<![\w.])5\.1(?![\w.])'), 6),
	(re.compile(r'(?<![\w.])7\.1(?![\w.])'), 8),
	(re.compile(r'\bmono\b', re.I), 1),
	(re.compile(r'\bstereo\b', re.I), 2),
)


def channels_from_title(title: str) -> int:
	"""The channel count a release track title names ("(5.1 Mix)", "Mono"), 0 if it names none. Discogs and
	MusicBrainz tracklists carry no channel field, but editions with several mixes put it in the title."""
	for pattern, channels in CHANNEL_HINTS:
		if pattern.search(title):
			return channels
	return 0


def touch(path: Path) -> None:
	"""Update the mtime after a save, so caches and sync tools notice the change."""
	try:
		os.utime(path, None)
	except OSError as e:
		log.warning('Could not touch file mtime for %s: %s', path, e)
