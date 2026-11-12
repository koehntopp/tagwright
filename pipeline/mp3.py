"""MP3 files behind the `Audio` interface of `pipeline/audio.py` (ADR 0058, 0059).

The rest of the program thinks in Vorbis-style tags: upper-case keys, lists of strings. ID3 has a fixed set of frames
plus `TXXX:<name>` for anything else. `Mp3Audio.tags` is a view that maps one onto the other:

- the usual fields (title, artist, album, date, genre, ...) are the matching text frames (`TEXT_FRAMES`);
- `TRACKNUMBER` / `TRACKTOTAL` / `TOTALTRACKS` are the two halves of `TRCK` ("3/12"), `DISCNUMBER` / `DISCTOTAL` /
  `TOTALDISCS` of `TPOS`;
- `LYRICS` is the `USLT` frame, `COMMENT` the `COMM` frame;
- every other key is a `TXXX` frame whose description is the key (`DYNAMIC_RANGE`, `REPLAYGAIN_ALBUM_GAIN`, the Discogs
  tags ...); on reading, a description in any case is a key.

Tags are written as ID3v2.4 (UTF-8, several values in one frame), so a multi-valued tag survives; v2.3 cannot store
that without joining the values with a separator that also occurs in them (ADR 0059). Keys come back lower-cased,
as with FLAC. The ID3v1 block of a file that has one is kept up to date by mutagen.
"""

import io
from collections.abc import Iterator, MutableMapping
from pathlib import Path

import mutagen.id3 as id3mod
from mutagen.flac import Picture
from mutagen.id3 import APIC, COMM, ID3, TXXX, USLT, Encoding, Frame, PictureType
from mutagen.mp3 import MP3
from PIL import Image, UnidentifiedImageError

UTF8 = Encoding.UTF8
LANG = 'eng'

# Vorbis key -> text frame. Keys not listed here are TXXX frames.
TEXT_FRAMES: dict[str, str] = {
	'TITLE': 'TIT2',
	'ARTIST': 'TPE1',
	'ALBUMARTIST': 'TPE2',
	'ALBUM': 'TALB',
	'DATE': 'TDRC',
	'ORIGINALDATE': 'TDOR',
	'GENRE': 'TCON',
	'COMPOSER': 'TCOM',
	'PUBLISHER': 'TPUB',
	'LABEL': 'TPUB',
	'COPYRIGHT': 'TCOP',
	'SUBTITLE': 'TIT3',
	'DISCSUBTITLE': 'TSST',
	'ENCODER': 'TSSE',
	'BPM': 'TBPM',
	'ISRC': 'TSRC',
	'LANGUAGE': 'TLAN',
	'MOOD': 'TMOO',
	'MEDIA': 'TMED',
	'ARTISTSORT': 'TSOP',
	'ALBUMARTISTSORT': 'TSO2',
	'ALBUMSORT': 'TSOA',
	'TITLESORT': 'TSOT',
	'COMPOSERSORT': 'TSOC',
	'LYRICIST': 'TEXT',
	'CONDUCTOR': 'TPE3',
	'REMIXER': 'TPE4',
	'GROUPING': 'TIT1',
}
KEY_OF_FRAME = {}
for _k, _f in TEXT_FRAMES.items():
	KEY_OF_FRAME.setdefault(_f, _k)  # LABEL and PUBLISHER share TPUB; the first one listed names it
NUMBER_FRAMES = {  # key -> (frame, part of "n/total")
	'TRACKNUMBER': ('TRCK', 0),
	'TRACKTOTAL': ('TRCK', 1),
	'TOTALTRACKS': ('TRCK', 1),
	'DISCNUMBER': ('TPOS', 0),
	'DISCTOTAL': ('TPOS', 1),
	'TOTALDISCS': ('TPOS', 1),
}


def _frame(name: str, **kw: object) -> Frame:
	return getattr(id3mod, name)(encoding=UTF8, **kw)


def _texts(frame: Frame) -> list[str]:
	return [str(x) for x in frame.text]


class TagView(MutableMapping[str, list[str]]):
	"""The Vorbis-style face of an ID3 tag block (see the module docstring)."""

	def __init__(self, id3: ID3) -> None:
		self.id3 = id3

	def _txxx(self, key: str) -> TXXX | None:
		for f in self.id3.getall('TXXX'):
			if f.desc.upper() == key:
				return f
		return None

	def _number(self, key: str) -> list[str]:
		frame, part = NUMBER_FRAMES[key]
		got = self.id3.getall(frame)
		if not got or not got[0].text:
			return []
		pieces = str(got[0].text[0]).split('/', 1)
		return [pieces[part].strip()] if len(pieces) > part and pieces[part].strip() else []

	def _set_number(self, key: str, value: str) -> None:
		frame, part = NUMBER_FRAMES[key]
		got = self.id3.getall(frame)
		pieces = (str(got[0].text[0]).split('/', 1) if got and got[0].text else []) + ['', '']
		number, total = pieces[0].strip(), pieces[1].strip()
		if part == 0:
			number, *rest = [p.strip() for p in value.split('/', 1)] + ['']
			total = rest[0] or total
		else:
			total = value.strip()
		text = f'{number}/{total}' if number and total else number or (f'/{total}' if total else '')
		self.id3.delall(frame)
		if text:
			self.id3.add(_frame(frame, text=[text]))

	def get_list(self, key: str) -> list[str]:
		key = key.upper()
		if key in NUMBER_FRAMES:
			return self._number(key)
		if key in TEXT_FRAMES:
			got = self.id3.getall(TEXT_FRAMES[key])
			return _texts(got[0]) if got else []
		if key == 'LYRICS':
			got = self.id3.getall('USLT')
			return [str(got[0].text)] if got and str(got[0].text) else []
		if key == 'COMMENT':
			got = sorted(self.id3.getall('COMM'), key=lambda f: f.desc != '')
			return [str(got[0].text[0])] if got and got[0].text else []
		f = self._txxx(key)
		return _texts(f) if f else []

	def __getitem__(self, key: str) -> list[str]:
		values = self.get_list(key)
		if not values:
			raise KeyError(key)
		return values

	def __setitem__(self, key: str, value: str | list[str]) -> None:
		key = key.upper()
		values = [value] if isinstance(value, str) else [str(x) for x in value]
		if key in NUMBER_FRAMES:
			if values:
				self._set_number(key, values[0])
			else:
				del self[key]
		elif key in TEXT_FRAMES:
			name = TEXT_FRAMES[key]
			self.id3.delall(name)
			if values:
				self.id3.add(_frame(name, text=values))
		elif key == 'LYRICS':
			self.id3.delall('USLT')
			if values:
				self.id3.add(USLT(encoding=UTF8, lang=LANG, desc='', text=values[0]))
		elif key == 'COMMENT':
			self.id3.delall('COMM')
			if values:
				self.id3.add(COMM(encoding=UTF8, lang=LANG, desc='', text=values))
		else:
			old = self._txxx(key)
			if old is not None:
				self.id3.delall(f'TXXX:{old.desc}')
			if values:
				self.id3.add(TXXX(encoding=UTF8, desc=key, text=values))

	def __delitem__(self, key: str) -> None:
		key = key.upper()
		if key in NUMBER_FRAMES:
			frame, part = NUMBER_FRAMES[key]
			if part == 0:
				self.id3.delall(frame)
			else:
				self._set_number(key, '')
		elif key in TEXT_FRAMES:
			self.id3.delall(TEXT_FRAMES[key])
		elif key == 'LYRICS':
			self.id3.delall('USLT')
		elif key == 'COMMENT':
			self.id3.delall('COMM')
		elif (f := self._txxx(key)) is not None:
			self.id3.delall(f'TXXX:{f.desc}')

	def __contains__(self, key: object) -> bool:
		return isinstance(key, str) and bool(self.get_list(key))

	def __iter__(self) -> Iterator[str]:
		seen: list[str] = []
		for f in self.id3.values():
			name = type(f).__name__
			if name in KEY_OF_FRAME:
				keys = [KEY_OF_FRAME[name]]
			elif name in ('TRCK', 'TPOS'):
				track = name == 'TRCK'
				keys = ['TRACKNUMBER' if track else 'DISCNUMBER']
				if self._number('TRACKTOTAL' if track else 'DISCTOTAL'):
					keys += ['TRACKTOTAL', 'TOTALTRACKS'] if track else ['DISCTOTAL', 'TOTALDISCS']
			elif name == 'USLT':
				keys = ['LYRICS']
			elif name == 'COMM':
				keys = ['COMMENT']
			elif name == 'TXXX':
				keys = [f.desc.upper()]
			else:
				continue
			for k in keys:
				if k.lower() not in seen:
					seen.append(k.lower())
					yield k.lower()

	def __len__(self) -> int:
		return sum(1 for _ in self)


class Mp3Info:
	"""The stream facts the program reads (the same names as mutagen's FLAC info)."""

	def __init__(self, mp3: MP3) -> None:
		self.length = float(mp3.info.length)
		self.channels = int(mp3.info.channels)
		self.sample_rate = int(mp3.info.sample_rate)
		self.bitrate = int(mp3.info.bitrate)


def _cover_of(apic: APIC) -> Picture:
	pic = Picture()
	pic.type, pic.mime, pic.desc, pic.data = int(apic.type), apic.mime, apic.desc, apic.data
	try:
		with Image.open(io.BytesIO(apic.data)) as im:
			pic.width, pic.height = im.size
			pic.depth = {'1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32, 'CMYK': 32}.get(im.mode, 24)
	except UnidentifiedImageError, OSError:
		pass  # not an image we can measure: the size stays 0, as for a FLAC picture without one
	return pic


class Mp3Audio:
	"""An MP3 file with the surface the program uses on a FLAC file."""

	def __init__(self, path: Path | str) -> None:
		self.filename = str(path)
		self._mp3 = MP3(self.filename)
		self.info = Mp3Info(self._mp3)
		self.tags: TagView | None = TagView(self._mp3.tags) if self._mp3.tags is not None else None

	def add_tags(self) -> None:
		if self._mp3.tags is None:
			self._mp3.add_tags()
		self.tags = TagView(self._mp3.tags)

	def _view(self) -> TagView:
		if self.tags is None:
			raise ValueError('the file has no tag block: call add_tags() first')
		return self.tags

	def __getitem__(self, key: str) -> list[str]:
		return self._view()[key]

	def __setitem__(self, key: str, value: str | list[str]) -> None:
		self._view()[key] = value

	def __delitem__(self, key: str) -> None:
		del self._view()[key]

	def __contains__(self, key: object) -> bool:
		return self.tags is not None and key in self.tags

	@property
	def pictures(self) -> list[Picture]:
		return (
			[_cover_of(a) for a in self._mp3.tags.getall('APIC')]
			if self._mp3.tags is not None
			else []
		)

	def clear_pictures(self) -> None:
		if self._mp3.tags is not None:
			self._mp3.tags.delall('APIC')

	def add_picture(self, pic: Picture) -> None:
		if self._mp3.tags is None:
			self.add_tags()
		self._mp3.tags.add(
			APIC(
				encoding=UTF8,
				mime=pic.mime,
				type=PictureType(pic.type),
				desc=pic.desc or '',
				data=pic.data,
			)
		)

	def save(self) -> None:
		self._mp3.save(v2_version=4)
