"""The path template: which tags make up the folders and the file name (ADR 0037, 0010).

A template has folder levels (each a list of chips), an optional disc folder that exists only for multi-disc
albums, and the file name. A chip is a tag with a format, or literal text. The default reproduces the layout of
the discogs `bliss.py`: `<album artist>/<album [version]>[/Disc <n>]/<disc>_<track>_<title>.flac`.
Tag values go through `pipeline.naming.clean()`, so names stay exactly what existing libraries were built with.
An empty tag never gets a placeholder: the file is "unplaced" until the tag is set (ADR 0010).
"""

import re
from dataclasses import dataclass, field

from pipeline.naming import clean

# The tags a template may use and the index keeps. ALBUM_VERSION is the bliss rule: ALBUM plus VERSION unless the
# album already contains it.
PALETTE: dict[str, str] = {
	'ALBUMARTIST': 'Album artist',
	'ARTIST': 'Artist',
	'ALBUM': 'Album',
	'VERSION': 'Version',
	'ALBUM_VERSION': 'Album + version',
	'ALBUM_EDITION': 'Edition',
	'ALBUM_FORMAT': 'Format',
	'CATALOGNUMBER': 'Catalog #',
	'DATE': 'Year',
	'ORIGINALDATE': 'Original year',
	'DISCNUMBER': 'Disc',
	'TRACKNUMBER': 'Track',
	'TITLE': 'Title',
	'DISCSUBTITLE': 'Disc subtitle',
}
# What the index stores per file: the palette (without the composite) and what multi-disc detection reads.
INDEXED_TAGS = (*(k for k in PALETTE if k != 'ALBUM_VERSION'), 'DISCTOTAL', 'TOTALDISCS')
FORMATS = (
	'text',
	'num',
	'int',
	'year',
)  # cleaned text; part before '/', zero-padded; leading integer; first 4 chars
MAX_LEVELS = 4
FORBIDDEN_LITERAL = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


class MissingTag(Exception):
	"""A chip's tag is empty; `tag` says which."""

	def __init__(self, tag: str) -> None:
		super().__init__(tag)
		self.tag = tag


@dataclass(frozen=True)
class Chip:
	tag: str = ''  # a PALETTE key; empty for a literal
	text: str = ''  # the literal, when tag is empty
	fmt: str = 'text'
	pad: int = 0  # zero padding for fmt 'num'
	fallback: str = ''  # another PALETTE key used when the tag is empty (off by default, ADR 0010)

	def to_dict(self) -> dict:
		if not self.tag:
			return {'text': self.text}
		d: dict = {'tag': self.tag, 'fmt': self.fmt}
		if self.pad:
			d['pad'] = self.pad
		if self.fallback:
			d['fallback'] = self.fallback
		return d

	@staticmethod
	def from_dict(d: dict) -> Chip:
		return Chip(
			tag=str(d.get('tag', '')),
			text=str(d.get('text', '')),
			fmt=str(d.get('fmt', 'text')),
			pad=int(d.get('pad', 0) or 0),
			fallback=str(d.get('fallback', '')),
		)


type Level = tuple[Chip, ...]


@dataclass(frozen=True)
class Template:
	folders: tuple[Level, ...]
	filename: Level
	disc_folder: Level | None = None  # only for albums that span several discs

	def to_dict(self) -> dict:
		return {
			'folders': [[c.to_dict() for c in level] for level in self.folders],
			'disc_folder': None
			if self.disc_folder is None
			else [c.to_dict() for c in self.disc_folder],
			'filename': [c.to_dict() for c in self.filename],
		}

	@staticmethod
	def from_dict(d: dict) -> Template:
		def level(raw: list) -> Level:
			return tuple(Chip.from_dict(c) for c in raw)

		disc = d.get('disc_folder')
		return Template(
			folders=tuple(level(x) for x in d.get('folders', [])),
			filename=level(d.get('filename', [])),
			disc_folder=None if disc is None else level(disc),
		)


def default() -> Template:
	"""The bliss layout (without the ARTIST fallback bliss has: ADR 0010 forbids it)."""
	return Template(
		folders=((Chip('ALBUMARTIST'),), (Chip('ALBUM_VERSION'),)),
		disc_folder=(Chip(text='Disc '), Chip('DISCNUMBER', fmt='int')),
		filename=(
			Chip('DISCNUMBER', fmt='num', pad=2),
			Chip(text='_'),
			Chip('TRACKNUMBER', fmt='num', pad=2),
			Chip(text='_'),
			Chip('TITLE'),
		),
	)


def validate(t: Template) -> tuple[list[str], list[str]]:
	"""(errors, warnings). Errors make the template unusable; warnings are shown but allowed."""
	errors: list[str] = []
	warnings: list[str] = []
	levels = [(f'folder level {i + 1}', lv) for i, lv in enumerate(t.folders)]
	if t.disc_folder is not None:
		levels.append(('disc folder', t.disc_folder))
	levels.append(('file name', t.filename))
	if not t.folders:
		errors.append('at least one folder level is needed')
	if len(t.folders) > MAX_LEVELS:
		errors.append(f'at most {MAX_LEVELS} folder levels')
	for name, level in levels:
		if not level:
			errors.append(f'{name} is empty')
		for c in level:
			if c.tag:
				if c.tag not in PALETTE:
					errors.append(f'{name}: unknown tag {c.tag}')
				if c.fallback and c.fallback not in PALETTE:
					errors.append(f'{name}: unknown fallback tag {c.fallback}')
				if c.fmt not in FORMATS:
					errors.append(f'{name}: unknown format {c.fmt}')
				if not 0 <= c.pad <= 6:
					errors.append(f'{name}: padding must be 0 to 6')
			elif not c.text or FORBIDDEN_LITERAL.search(c.text):
				errors.append(f'{name}: text must be non-empty without / \\ : * ? " < > |')
		if level and not any(c.tag for c in level):
			errors.append(f'{name} needs at least one tag')
	tags = {c.tag for c in t.filename}
	if 'TITLE' not in tags:
		warnings.append('the file name has no title: names are less readable')
	if not ({'TRACKNUMBER', 'TITLE'} <= tags):
		warnings.append(
			'without track and title in the file name, tracks of one album can get the same name'
		)
	if 'DISCNUMBER' not in tags and t.disc_folder is None:
		warnings.append(
			'without a disc number in the file name or a disc folder, multi-disc albums collide'
		)
	return errors, warnings


def _leading(value: str) -> str:
	m = re.match(r'\s*(\d+)', value)
	return m.group(1) if m else ''


def _value(tags: dict[str, str], tag: str) -> str:
	if tag == 'ALBUM_VERSION':
		album, version = tags.get('ALBUM', ''), tags.get('VERSION', '')
		return f'{album} {version}' if album and version and version not in album else album
	return tags.get(tag, '')


def render_level(level: Level, tags: dict[str, str]) -> str:
	"""One path component (or file name stem). Raises MissingTag when a chip's tag is empty."""
	out = []
	for c in level:
		if not c.tag:
			out.append(c.text)
			continue
		raw = _value(tags, c.tag).strip() or (
			_value(tags, c.fallback).strip() if c.fallback else ''
		)
		if not raw:
			raise MissingTag(c.tag)
		if c.fmt == 'num':
			out.append(raw.split('/')[0].zfill(c.pad))
		elif c.fmt == 'int':
			n = _leading(raw)
			if not n:
				raise MissingTag(c.tag)
			out.append(str(int(n)))
		elif c.fmt == 'year':
			out.append(clean(raw[:4]))
		else:
			out.append(clean(raw))
	return ''.join(out)


@dataclass(frozen=True)
class Target:
	"""Where a file belongs: the album folder (a tuple of components), the disc folder if any, the file name."""

	album_dir: tuple[str, ...]
	disc_dir: str
	filename: str
	extra: dict = field(default_factory=dict, compare=False)


def target(t: Template, tags: dict[str, str]) -> Target:
	"""The folder levels, the disc folder and the file name of a file; raises MissingTag, or ValueError for an
	empty component (a title or album that is nothing but symbols)."""
	album_dir = tuple(render_level(level, tags) for level in t.folders)
	disc_dir = render_level(t.disc_folder, tags) if t.disc_folder is not None else ''
	stem = render_level(t.filename, tags)
	if not stem or not all(album_dir):
		raise ValueError('a name is empty after cleaning')
	return Target(album_dir, disc_dir, f'{stem}.flac')
