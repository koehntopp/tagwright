"""Embedded cover art: resize pictures larger than the configured size (ADR 0016, 0036)."""

import io
import logging
from pathlib import Path

from mutagen import MutagenError
from PIL import Image, ImageFile

from pipeline.audio import Cover, new_cover, open_audio
from pipeline.layout import flacs

ImageFile.LOAD_TRUNCATED_IMAGES = True  # a cut-off download is better resized than skipped

log = logging.getLogger(__name__)

MIN_IMAGE_BYTES = 100  # anything smaller is not a picture worth decoding


def resize_covers(album: Path, max_size: int) -> int:
	"""Resize embedded covers in every FLAC of the album that are larger than max_size px (JPEG, quality 90).

	Pictures that are not JPEG/PNG, are tiny, cannot be decoded or are small enough stay as they are.
	Returns the number of files that were rewritten.
	"""
	rewritten = 0
	for flac_path in flacs(album):
		try:
			audio = open_audio(flac_path)
			if not audio.pictures:
				continue
			changed = False
			pictures = []
			for pic in audio.pictures:
				new = resized(pic, max_size, flac_path)
				changed = changed or new is not pic
				pictures.append(new)
			if changed:
				audio.clear_pictures()
				for pic in pictures:
					audio.add_picture(pic)
				audio.save()
				rewritten += 1
				log.info('Album art resized to at most %dx%d in %s', max_size, max_size, album.name)
		except (MutagenError, OSError) as e:
			log.warning('Cover resize failed for %s: %s', flac_path, e)
	return rewritten


def resized(pic: Cover, max_size: int, path: Path) -> Cover:
	"""The picture itself when it is small enough (or not a JPEG/PNG it can decode), else a JPEG at most
	max_size on either side."""
	if (
		pic.mime not in ('image/jpeg', 'image/png')
		or not pic.data
		or len(pic.data) < MIN_IMAGE_BYTES
	):
		return pic
	try:
		img = Image.open(io.BytesIO(pic.data))
		img.load()
	except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as err:
		log.warning('Corrupt or unparseable embedded image in %s: %s', path, err)
		return pic
	if img.width <= max_size and img.height <= max_size:
		return pic
	img.thumbnail((max_size, max_size), Image.LANCZOS)
	buf = io.BytesIO()
	img.convert('RGB').save(buf, format='JPEG', quality=90)
	new = new_cover()
	new.type = pic.type
	new.desc = pic.desc
	new.mime = 'image/jpeg'
	new.width, new.height = img.size
	new.depth = 24
	new.data = buf.getvalue()
	return new
