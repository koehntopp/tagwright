"""A cover that is dropped or fetched is scaled to the cover limit at once (ADR 0016)."""

import io
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from mutagen.flac import FLAC
from PIL import Image

import app as tagwright


def image(width: int, height: int, fmt: str = 'JPEG', mode: str = 'RGB') -> bytes:
	buf = io.BytesIO()
	Image.new(mode, (width, height), 'blue').save(buf, format=fmt)
	return buf.getvalue()


def put(client: TestClient, album: Path, data: bytes) -> dict:
	r = client.put('/api/cover', params={'path': str(album)}, content=data)
	assert r.status_code == 200, r.text
	return r.json()


def test_a_large_cover_is_scaled_down_to_the_limit_on_upload(
	client: TestClient, album: Path
) -> None:
	s = put(client, album, image(4000, 3000))
	for f in tagwright.flacs(album):
		pic = FLAC(f).pictures[0]
		assert (pic.width, pic.height, pic.mime) == (1500, 1125, 'image/jpeg')
		assert Image.open(io.BytesIO(pic.data)).size == (1500, 1125)
	assert (s['cover']['w'], s['cover']['h']) == (1500, 1125)
	assert s['status'] == 'fixed'


def test_a_cover_within_the_limit_is_embedded_untouched(client: TestClient, album: Path) -> None:
	data = image(1400, 1400)
	put(client, album, data)
	assert FLAC(tagwright.flacs(album)[0]).pictures[0].data == data


def test_a_large_png_with_transparency_becomes_a_jpeg_at_the_limit(
	client: TestClient, album: Path
) -> None:
	put(client, album, image(2000, 2000, 'PNG', 'RGBA'))
	pic = FLAC(tagwright.flacs(album)[0]).pictures[0]
	assert (pic.width, pic.mime) == (1500, 'image/jpeg')


def test_a_large_image_of_another_format_is_converted_and_scaled(
	client: TestClient, album: Path
) -> None:
	put(client, album, image(3000, 3000, 'WEBP'))
	pic = FLAC(tagwright.flacs(album)[0]).pictures[0]
	assert (pic.width, pic.height, pic.mime) == (1500, 1500, 'image/jpeg')


def test_something_that_is_not_an_image_is_still_refused() -> None:
	with pytest.raises(HTTPException) as err:
		tagwright.make_picture(b'not an image')
	assert err.value.status_code == 400


def test_other_pictures_of_the_files_stay(client: TestClient, album: Path) -> None:
	from mutagen.flac import Picture

	back = Picture()
	back.type, back.mime, back.data = 4, 'image/jpeg', image(2000, 2000)
	back.width = back.height = 2000
	for f in tagwright.flacs(album):
		audio = FLAC(f)
		audio.add_picture(back)
		audio.save()
	put(client, album, image(3000, 3000))
	pics = FLAC(tagwright.flacs(album)[0]).pictures
	assert sorted(p.type for p in pics) == [3, 4]
	assert next(p for p in pics if p.type == 4).width == 2000  # only the front cover is touched
