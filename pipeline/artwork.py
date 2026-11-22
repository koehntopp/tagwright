"""Embedded artwork by picture type, and the cover files written beside an album in the library.

Pictures live in the audio files, not on disk: that is the source of truth (ADR 0090, 0091). Reading groups the
pictures of all files of an album by type, drops byte-identical repeats and keeps first-seen order. Writing a type
rewrites only that type in every file, so artwork the app does not own is never touched (ADR 0004).
"""

import hashlib
import io
import logging
import re
from pathlib import Path

from mutagen import MutagenError
from PIL import Image, UnidentifiedImageError

from pipeline.audio import Audio, Cover, new_cover, open_audio
from pipeline.covers import resized
from pipeline.layout import flacs
from pipeline.tagio import tag

log = logging.getLogger(__name__)

FRONT = 3
BACK = 4
LEAFLET = 5
MEDIA = 6
UNTYPED = 0
TYPES = (FRONT, BACK, LEAFLET, MEDIA)
KEYS = {FRONT: 'front', BACK: 'back', LEAFLET: 'leaflet', MEDIA: 'media'}
LABELS = {FRONT: 'Front Cover', BACK: 'Back Cover', LEAFLET: 'Leaflet', MEDIA: 'Media'}
JPEG_MAGIC = b'\xff\xd8'


def disc_of(audio: Audio) -> int:
	"""The disc of a file: the leading number of DISCNUMBER, else disc 1 (ADR 0098)."""
	m = re.match(r'\s*(\d+)', tag(audio.tags or {}, 'DISCNUMBER'))
	return int(m[1]) if m else 1


def discs(album: Path) -> list[int]:
	"""The disc numbers the album's files carry, sorted (ADR 0098)."""
	found = set()
	for path in flacs(album):
		try:
			found.add(disc_of(open_audio(path)))
		except (MutagenError, OSError, ValueError) as e:
			log.warning('Could not read %s: %s', path, e)
	return sorted(found)


def read(album: Path, disc: int | None = None) -> dict[int, list[Cover]]:
	"""The distinct pictures of the album (or of one disc) by type, in file order then picture order (ADR 0090,
	0098)."""
	return read_files(flacs(album), disc)


def read_files(paths: list[Path], disc: int | None = None) -> dict[int, list[Cover]]:
	"""The distinct pictures of these files by type; with `disc`, only the files of that disc."""
	out: dict[int, list[Cover]] = {t: [] for t in (*TYPES, UNTYPED)}
	seen: dict[int, set[str]] = {t: set() for t in out}
	for path in paths:
		try:
			audio = open_audio(path)
			if disc is not None and disc_of(audio) != disc:
				continue
			pictures = audio.pictures
		except (MutagenError, OSError, ValueError) as e:
			log.warning('Could not read the pictures of %s: %s', path, e)
			continue
		for pic in pictures:
			if pic.type not in out or not pic.data:
				continue
			key = hashlib.sha256(pic.data).hexdigest()
			if key in seen[pic.type]:
				continue
			seen[pic.type].add(key)
			out[pic.type].append(pic)
	return out


def info(pic: Cover) -> dict:
	"""The size of a picture, decoding it only when mutagen left the dimensions unset."""
	w, h = pic.width, pic.height
	if not (w and h):
		try:
			with Image.open(io.BytesIO(pic.data)) as im:
				w, h = im.width, im.height
		except OSError, ValueError, UnidentifiedImageError:
			w, h = 0, 0
	return {'w': w, 'h': h, 'bytes': len(pic.data)}


def picture(data: bytes, type_: int, max_size: int) -> Cover:
	"""A picture of `type_` from image bytes: JPEG and PNG are kept, anything else becomes JPEG, and an image over
	`max_size` is scaled at once (ADR 0042, 0090)."""
	try:
		with Image.open(io.BytesIO(data)) as im:
			fmt, w, h, mode = im.format, im.width, im.height, im.mode
			if fmt not in ('JPEG', 'PNG'):
				buf = io.BytesIO()
				im.convert('RGB').save(buf, 'JPEG', quality=95)
				data, fmt, mode = buf.getvalue(), 'JPEG', 'RGB'
	except (OSError, UnidentifiedImageError) as e:
		raise ValueError('not a readable image') from e
	pic = new_cover()
	pic.type, pic.mime, pic.desc, pic.width, pic.height, pic.data = (
		type_,
		f'image/{fmt.lower()}',
		'',
		w,
		h,
		data,
	)
	pic.depth = {'1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32}.get(mode, 24)
	return resized(pic, max_size, Path('cover'))


def write(album: Path, type_: int, pictures: list[Cover], disc: int | None = None) -> None:
	"""Put `pictures` of one type into every audio file of the album, or of one disc (ADR 0098); other types stay.
	Type 0 is removed when the front cover is written, as the old front-cover replace did (ADR 0016)."""
	for path in flacs(album):
		try:
			audio = open_audio(path)
			if disc is not None and disc_of(audio) != disc:
				continue
			old = audio.pictures
			keep = [
				p for p in old if p.type != type_ and not (type_ == FRONT and p.type == UNTYPED)
			]
			wanted = [*keep, *pictures]
			if [(p.type, p.data) for p in old] == [(p.type, p.data) for p in wanted]:
				continue
			audio.clear_pictures()
			for pic in wanted:
				audio.add_picture(pic)
			audio.save()
		except (MutagenError, OSError, ValueError) as e:
			log.warning('Could not write the artwork of %s: %s', path, e)


def front_picture(groups: dict[int, list[Cover]]) -> Cover | None:
	"""The front cover: type 3, else an untyped picture from an older tagger (ADR 0090)."""
	return next(iter(groups[FRONT]), None) or next(iter(groups[UNTYPED]), None)


def sidecar_names(groups: dict[int, list[Cover]]) -> list[tuple[str, Cover]]:
	"""The artwork files to write under an album: `folder.jpg` for the front, then numbered `Artwork/` files
	for back, leaflet and media in type order (ADR 0091)."""
	out: list[tuple[str, Cover]] = []
	if pic := front_picture(groups):
		out.append(('folder.jpg', pic))
	counters = {BACK: 0, LEAFLET: 0, MEDIA: 0}
	names = {BACK: 'back', LEAFLET: 'booklet', MEDIA: 'disc'}
	index = 0
	for type_ in (BACK, LEAFLET, MEDIA):
		for pic in groups[type_]:
			index += 1
			counters[type_] += 1
			n = counters[type_]
			stem = names[type_]
			suffix = f'-{n:02d}' if n > 1 or type_ == LEAFLET else ''
			out.append((f'Artwork/{index:02d} {stem}{suffix}.jpg', pic))
	return out


def _write_image(path: Path, pic: Cover, overwrite: bool = False) -> None:
	"""Write one sidecar as JPEG; an existing file is replaced only with `overwrite` (ADR 0091, 0098)."""
	path.parent.mkdir(parents=True, exist_ok=True)
	data = pic.data
	if not data.startswith(JPEG_MAGIC):
		try:
			with Image.open(io.BytesIO(data)) as im:
				buf = io.BytesIO()
				im.convert('RGB').save(buf, 'JPEG', quality=90)
				data = buf.getvalue()
		except OSError, ValueError, UnidentifiedImageError:
			pass  # keep the original bytes rather than lose the art
	with path.open('wb' if overwrite else 'xb') as out:
		out.write(data)


def folder_sets(album_dir: Path, by_dir: dict[Path, list[Path]]) -> list[tuple[Path, Cover]]:
	"""The cover files of an album whose audio files sit in the folders of `by_dir` (ADR 0098): every folder gets
	the set of its own files; when the album folder itself holds no audio (disc folders), it gets only folder.jpg,
	the front cover of the first disc folder."""
	out: list[tuple[Path, Cover]] = []
	first_front = None
	for d in sorted(by_dir):
		groups = read_files(by_dir[d])
		out += [(d / name, pic) for name, pic in sidecar_names(groups)]
		if first_front is None:
			first_front = front_picture(groups)
	if album_dir not in by_dir and first_front is not None:
		out.insert(0, (album_dir / 'folder.jpg', first_front))
	return out


def _by_dir(album_dir: Path) -> dict[Path, list[Path]]:
	by_dir: dict[Path, list[Path]] = {}
	for path in flacs(album_dir):
		by_dir.setdefault(path.parent, []).append(path)
	return by_dir


def plan(album_dir: Path, moves: list[tuple[Path, Path]]) -> list[str]:
	"""The cover files a move of (source, destination) audio files into `album_dir` would create, relative to it
	(ADR 0091, 0098). Nothing is written."""
	by_dir: dict[Path, list[Path]] = {}
	for src, dst in moves:
		by_dir.setdefault(dst.parent, []).append(src)
	return [
		path.relative_to(album_dir).as_posix()
		for path, _ in folder_sets(album_dir, by_dir)
		if not path.exists()
	]


def export(album_dir: Path) -> list[str]:
	"""Create the missing cover files of an album in place from its embedded art; existing files stay (ADR 0091)."""
	return _write_all(album_dir, folder_sets(album_dir, _by_dir(album_dir)), overwrite=False)


def export_groups(groups: dict[int, list[Cover]], target: Path) -> list[str]:
	"""Write the missing sidecars of one folder for pictures read earlier (ADR 0091)."""
	return _write_all(target, [(target / n, p) for n, p in sidecar_names(groups)], overwrite=False)


def rebuild(album_dir: Path) -> list[str]:
	"""Make a library album's cover files match its embedded art (ADR 0098): rewrite every file, delete folder.jpg
	and Artwork/ files no picture backs any more, and remove an emptied Artwork/ folder."""
	by_dir = _by_dir(album_dir)
	items = folder_sets(album_dir, by_dir)
	wanted = {path for path, _ in items}
	for d in {album_dir, *by_dir}:
		art = d / 'Artwork'
		stale = [d / 'folder.jpg', *(art.iterdir() if art.is_dir() else [])]
		for path in stale:
			if path not in wanted and path.is_file():
				try:
					path.unlink()
					log.info('Removed the stale artwork file %s', path)
				except OSError as e:
					log.warning('Could not remove %s: %s', path, e)
		if art.is_dir() and not any(art.iterdir()):
			art.rmdir()
	return _write_all(album_dir, items, overwrite=True)


def _write_all(base: Path, items: list[tuple[Path, Cover]], overwrite: bool) -> list[str]:
	written: list[str] = []
	for dst, pic in items:
		if dst.exists() and not overwrite:
			continue
		try:
			_write_image(dst, pic, overwrite)
			written.append(dst.relative_to(base).as_posix())
		except OSError as e:
			log.warning('Could not write %s: %s', dst, e)
	if written:
		log.info('Wrote %d artwork file(s) for %s', len(written), base.name)
	return written
