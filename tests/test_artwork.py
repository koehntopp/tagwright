"""Embedded artwork by type and the cover files written when an album moves (ADR 0090, 0091)."""

import io
from pathlib import Path

from fastapi.testclient import TestClient
from mutagen.flac import FLAC, Picture
from PIL import Image

import app as tagwright
from pipeline import artwork

from .conftest import MakeFlac


def image(color: str) -> bytes:
	buf = io.BytesIO()
	Image.new('RGB', (8, 8), color).save(buf, format='JPEG')
	return buf.getvalue()


def add_picture(album: Path, type_: int, data: bytes) -> None:
	pic = Picture()
	pic.type, pic.mime, pic.data = type_, 'image/jpeg', data
	pic.width = pic.height = 8
	for f in tagwright.flacs(album):
		audio = FLAC(f)
		audio.add_picture(pic)
		audio.save()


def pic(type_: int, data: bytes) -> Picture:
	out = Picture()
	out.type, out.mime, out.data = type_, 'image/jpeg', data
	return out


def test_read_groups_by_type_and_drops_repeated_bytes(album: Path) -> None:
	front, back, leaf1, leaf2 = (image(c) for c in ('red', 'green', 'blue', 'yellow'))
	add_picture(album, artwork.FRONT, front)  # the same bytes in every file
	add_picture(album, artwork.BACK, back)
	audio = FLAC(tagwright.flacs(album)[0])
	audio.add_picture(pic(artwork.LEAFLET, leaf1))
	audio.add_picture(pic(artwork.LEAFLET, leaf2))
	audio.save()
	groups = artwork.read(album)
	assert [p.data for p in groups[artwork.FRONT]] == [front]
	assert [p.data for p in groups[artwork.BACK]] == [back]
	assert [p.data for p in groups[artwork.LEAFLET]] == [leaf1, leaf2]
	assert groups[artwork.MEDIA] == []


def test_typed_put_and_delete_touch_only_that_type(client: TestClient, album: Path) -> None:
	front = image('red')
	add_picture(album, artwork.FRONT, front)
	leaf1, leaf2 = image('blue'), image('yellow')
	for data in (leaf1, leaf2):
		r = client.put(
			'/api/cover',
			params={'path': str(album), 'type': artwork.LEAFLET},
			content=data,
		)
		assert r.status_code == 200, r.text
	items = client.get('/api/covers', params={'path': str(album)}).json()['leaflet']
	assert len(items) == 2
	r = client.put(
		'/api/cover',
		params={'path': str(album), 'type': artwork.LEAFLET, 'index': 0},
		content=image('purple'),
	)
	assert r.status_code == 200, r.text
	types = [p.type for p in FLAC(tagwright.flacs(album)[0]).pictures]
	assert sorted(types) == [3, 5, 5]
	r = client.request(
		'DELETE',
		'/api/cover',
		params={'path': str(album), 'type': artwork.LEAFLET, 'index': 1},
	)
	assert r.status_code == 200, r.text
	types = [p.type for p in FLAC(tagwright.flacs(album)[0]).pictures]
	assert sorted(types) == [3, 5]
	assert next(p for p in FLAC(tagwright.flacs(album)[0]).pictures if p.type == 3).data == front


def test_export_names_artwork_and_never_overwrites(tmp_path: Path) -> None:
	front, back, leaf1, leaf2, disc = (image(c) for c in ('red', 'green', 'blue', 'yellow', 'gray'))
	groups = {
		artwork.FRONT: [pic(artwork.FRONT, front)],
		artwork.BACK: [pic(artwork.BACK, back)],
		artwork.LEAFLET: [pic(artwork.LEAFLET, leaf1), pic(artwork.LEAFLET, leaf2)],
		artwork.MEDIA: [pic(artwork.MEDIA, disc)],
		artwork.UNTYPED: [],
	}
	target = tmp_path / 'Album'
	assert artwork.export_groups(groups, target) == [
		'folder.jpg',
		'Artwork/01 back.jpg',
		'Artwork/02 booklet-01.jpg',
		'Artwork/03 booklet-02.jpg',
		'Artwork/04 disc.jpg',
	]
	assert (target / 'folder.jpg').read_bytes() == front
	(target / 'folder.jpg').write_bytes(b'owner copy')
	artwork.export_groups(groups, target)
	assert (target / 'folder.jpg').read_bytes() == b'owner copy'


def test_watcher_moves_recreate_embedded_artwork(make_flac: MakeFlac, tmp_path: Path) -> None:
	from pathlib import PurePosixPath

	from library.executor import Executor
	from library.planner import Move

	root = tmp_path / 'library'
	path = make_flac(root / 'dump' / '01.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	front = image('red')
	pic_ = pic(artwork.FRONT, front)
	audio = FLAC(path)
	audio.add_picture(pic_)
	audio.save()
	Executor(root).run([Move(PurePosixPath('dump/01.flac'), PurePosixPath('A/Al/01.flac'), False)])
	assert (root / 'A' / 'Al' / 'folder.jpg').read_bytes() == front


def test_move_recreates_embedded_artwork_in_the_library(
	client: TestClient, album: Path, make_flac: MakeFlac
) -> None:
	front, back = image('red'), image('green')
	add_picture(album, artwork.FRONT, front)
	add_picture(album, artwork.BACK, back)
	preview = client.get('/api/move/preview', params={'path': str(album)}).json()
	assert preview['artwork'] == ['folder.jpg', 'Artwork/01 back.jpg']
	r = client.post('/api/move', json={'path': str(album)})
	assert r.status_code == 200, r.text
	where = Path(r.json()['moved_to'])
	assert (where / 'folder.jpg').read_bytes() == front
	assert (where / 'Artwork' / '01 back.jpg').read_bytes() == back


def test_a_disc_edit_touches_only_that_discs_files(client: TestClient, album: Path) -> None:
	"""ADR 0098: with `disc`, covers are read and written for that disc's files only."""
	one, two = tagwright.flacs(album)
	for f, d in ((one, '1'), (two, '2/2')):
		audio = FLAC(f)
		audio['DISCNUMBER'] = [d]
		audio.save()
	label = image('blue')
	r = client.put(
		'/api/cover', params={'path': str(album), 'type': artwork.MEDIA, 'disc': 2}, content=label
	)
	assert r.status_code == 200, r.text
	assert [p.type for p in FLAC(one).pictures] == []
	assert [p.type for p in FLAC(two).pictures] == [artwork.MEDIA]
	covers = client.get('/api/covers', params={'path': str(album), 'disc': 1}).json()
	assert covers['discs'] == [1, 2] and covers['media'] == []
	assert len(client.get('/api/covers', params={'path': str(album)}).json()['media']) == 1
	r = client.put(
		'/api/cover', params={'path': str(album), 'type': artwork.FRONT, 'disc': 1}, content=label
	)
	assert [p.type for p in FLAC(one).pictures] == [artwork.FRONT]
	assert [p.type for p in FLAC(two).pictures] == [artwork.MEDIA]


def test_an_edit_on_a_library_album_rebuilds_its_cover_files_per_disc_folder(
	client: TestClient, make_flac: MakeFlac
) -> None:
	"""ADR 0098: disc folders get their own set, the album folder only folder.jpg; stale files go."""
	album = tagwright.INGEST / 'A' / 'Al'
	make_flac(album / 'Disc 1' / '01.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	make_flac(album / 'Disc 2' / '01.flac', TITLE='Two', TRACKNUMBER='1', DISCNUMBER='2')
	(album / 'Artwork').mkdir()
	(album / 'Artwork' / '01 back.jpg').write_bytes(b'old')
	front, label = image('red'), image('blue')
	client.put('/api/cover', params={'path': str(album)}, content=front)
	client.put(
		'/api/cover', params={'path': str(album), 'type': artwork.MEDIA, 'disc': 2}, content=label
	)
	assert (album / 'folder.jpg').exists() and (album / 'Disc 1' / 'folder.jpg').exists()
	assert (album / 'Disc 2' / 'Artwork' / '01 disc.jpg').exists()
	assert not (album / 'Artwork').exists()
	assert not (album / 'Disc 1' / 'Artwork').exists()
	client.delete(
		'/api/cover', params={'path': str(album), 'type': artwork.MEDIA, 'index': 0, 'disc': 2}
	)
	assert not (album / 'Disc 2' / 'Artwork').exists()
	assert (album / 'Disc 2' / 'folder.jpg').exists()


def test_the_box_cover_sits_after_the_disc_cover_and_fills_the_top_folder(
	client: TestClient, make_flac: MakeFlac
) -> None:
	"""ADR 0099: the box cover is a front described `Box set` in every file, after the disc's own front; the
	album folder shows it, a disc folder without its own front falls back to it."""
	album = tagwright.INGEST / 'A' / 'Box'
	one = make_flac(album / 'Disc 1' / '01.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	two = make_flac(album / 'Disc 2' / '01.flac', TITLE='Two', TRACKNUMBER='1', DISCNUMBER='2')
	box, disc1 = image('red'), image('blue')
	put = {'path': str(album), 'type': artwork.BOX}
	assert client.put('/api/cover', params=put, content=box).status_code == 200
	client.put('/api/cover', params={'path': str(album), 'type': 3, 'disc': 1}, content=disc1)
	assert [(p.type, p.desc) for p in FLAC(one).pictures] == [(3, ''), (3, 'Box set')]
	assert [(p.type, p.desc) for p in FLAC(two).pictures] == [(3, 'Box set')]
	covers = client.get('/api/covers', params={'path': str(album)}).json()
	assert len(covers['box']) == 1 and len(covers['front']) == 1
	top = (album / 'folder.jpg').read_bytes()
	assert top == client.get('/api/cover', params=put | {'index': 0}).content
	assert top != (album / 'Disc 1' / 'folder.jpg').read_bytes()
	assert (album / 'Disc 2' / 'folder.jpg').read_bytes() == top
	client.put(
		'/api/cover', params={'path': str(album), 'type': 3, 'disc': 1}, content=image('green')
	)
	assert [p.desc for p in FLAC(one).pictures] == ['', 'Box set']  # a disc edit keeps the box
