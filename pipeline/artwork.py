"""Embedded artwork by picture type, and the cover files written beside an album in the library.

Pictures live in the audio files, not on disk: that is the source of truth (ADR 0090, 0091). Reading groups the
pictures of all files of an album by type, drops byte-identical repeats and keeps first-seen order. Writing a type
rewrites only that type in every file, so artwork the app does not own is never touched (ADR 0004).
"""

import hashlib
import io
import logging
from pathlib import Path

from mutagen import MutagenError
from PIL import Image, UnidentifiedImageError

from pipeline.audio import Cover, new_cover, open_audio
from pipeline.covers import resized
from pipeline.layout import flacs

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


def read(album: Path) -> dict[int, list[Cover]]:
	"""The distinct pictures of the album by type, in file order then picture order (ADR 0090)."""
	out: dict[int, list[Cover]] = {t: [] for t in (*TYPES, UNTYPED)}
	seen: dict[int, set[str]] = {t: set() for t in out}
	for path in flacs(album):
		try:
			audio = open_audio(path)
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


def write(album: Path, type_: int, pictures: list[Cover]) -> None:
	"""Put `pictures` of one type into every audio file of the album; other types stay. Type 0 is removed when the
	front cover is written, as the old front-cover replace did (ADR 0016)."""
	for path in flacs(album):
		try:
			audio = open_audio(path)
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


def _write_image(path: Path, pic: Cover) -> None:
	"""Write one sidecar as JPEG, without ever replacing a file that is already there (ADR 0091)."""
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
	with path.open('xb') as out:
		out.write(data)


def plan(album: Path, target: Path) -> list[str]:
	"""The sidecar paths an export of `album` into `target` would create (ADR 0091). Nothing is written."""
	return [name for name, _ in sidecar_names(read(album)) if not (target / name).exists()]


def export(album: Path, target: Path) -> list[str]:
	"""Recreate the cover files of `album` under `target` from its embedded art; existing files are left alone."""
	return export_groups(read(album), target)


def export_groups(groups: dict[int, list[Cover]], target: Path) -> list[str]:
	"""Write the sidecars for pictures read earlier, before the audio files moved away (ADR 0091)."""
	written: list[str] = []
	for name, pic in sidecar_names(groups):
		dst = target / name
		if dst.exists():
			continue
		try:
			_write_image(dst, pic)
			written.append(name)
		except OSError as e:
			log.warning('Could not write %s: %s', dst, e)
	if written:
		log.info('Wrote %d artwork file(s) for %s', len(written), target.name)
	return written
