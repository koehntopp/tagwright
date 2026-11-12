"""File names after the fixes: the bliss pattern `<disc>_<track>_<title>.flac` (ADR 0010).

`clean()` is the rule of the discogs `bliss.clean()` Tagwright replaces, unchanged, so existing libraries keep
their names. An empty tag means the album is not ready; nothing is invented (no "Unknown Title", no track 00).
"""

import unicodedata
from collections.abc import Callable
from pathlib import Path

from pathvalidate import sanitize_filename
from slugify import slugify

from pipeline.audio import open_audio
from pipeline.layout import flacs
from pipeline.tagio import Tags, tag


def clean(text: str) -> str:
	return sanitize_filename(slugify(text, lowercase=False, separator='_'))


def bliss_name(t: Tags) -> str | None:
	"""Bliss file name <disc>_<track>_<title>.flac, or None while TITLE, TRACKNUMBER or DISCNUMBER is empty."""
	title, number, disc = tag(t, 'TITLE'), tag(t, 'TRACKNUMBER'), tag(t, 'DISCNUMBER')
	if not title or not number or not disc:
		return None
	return f'{disc.split("/")[0].zfill(2)}_{number.split("/")[0].zfill(2)}_{clean(title)}.flac'


def bliss_album(t: Tags) -> str:
	"""Bliss library path <album artist>/<album [version]>, or '' while ALBUMARTIST or ALBUM is empty (not ready)."""
	album, artist = tag(t, 'ALBUM'), tag(t, 'ALBUMARTIST')
	if not album or not artist:
		return ''
	ver = tag(t, 'VERSION')
	if ver and ver not in album:
		album = f'{album} {ver}'
	return f'{clean(artist)}/{clean(album)}'


def same_name(a: str, b: str) -> bool:
	"""Equal ignoring case and Unicode normalization form (a case-insensitive volume sees these as one file)."""

	def n(x: str) -> str:
		return unicodedata.normalize('NFD', x.lower())

	return n(a) == n(b)


def rename_files(album: Path, name_of: Callable[[Tags], str | None] = bliss_name) -> list[str]:
	"""Rename FLACs in place to the name `name_of` gives (the bliss pattern by default). Returns log lines."""
	out = []
	for f in flacs(album):
		new = name_of(open_audio(f).tags or {})
		if new is None:
			out.append(f'skip {f.name}: title or track number is empty')
			continue
		if f.name == new:
			continue
		dest = f.with_name(new)
		if dest.exists() and not same_name(str(dest), str(f)):
			out.append(f'skip {f.name}: {new} already exists')
			continue
		f.rename(dest)
		out.append(f'renamed {f.name} -> {new}')
	return out or ['filenames already match']
