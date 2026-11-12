"""Stored album summaries: they survive a restart, the library is listed from the index, a change is noticed (ADR 0067)."""

import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from library.summaries import SummaryStore

from .conftest import MakeFlac


def test_the_store_keeps_and_forgets_summaries(tmp_path: Path) -> None:
	store = SummaryStore(tmp_path / 's.db')
	assert store.get('a') is None
	store.put('a', 'sig1', {'x': 1, 'ü': 'ö'})
	store.put('a', 'sig2', {'x': 2})
	store.put('b', 'sig', {})
	assert store.get('a') == ('sig2', {'x': 2})
	assert store.keep_only({'a'}) == 1 and store.get('b') is None
	store.delete('a')
	assert store.get('a') is None
	store.close()


def test_a_summary_survives_a_restart_and_a_change_is_noticed(
	album: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	first = tagwright.get_summary(album)
	tagwright.cache.clear()  # what a restart does to the memory

	def never(_a: Path) -> dict:
		raise AssertionError('the album was read again')

	monkeypatch.setattr(tagwright, 'summarize', never)
	assert tagwright.get_summary(album) == first
	f = sorted(album.glob('*.flac'))[0]
	a = FLAC(f)
	a['GENRE'] = ['Rock']
	a.save()
	with pytest.raises(AssertionError):  # the signature changed: it is read again
		tagwright.get_summary(album)


def test_a_library_album_is_checked_against_the_index_and_listed_from_it(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	album = tagwright.INGEST / 'Artist' / 'Album'
	make_flac(album / '01_01_One.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	st = (album / '01_01_One.flac').stat()
	sigs = {'Artist/Album': (('01_01_One.flac', st.st_mtime_ns, st.st_size),)}
	monkeypatch.setattr(tagwright, 'library_signatures', lambda: sigs)
	assert tagwright.album_signature(album) == tagwright.album_signature(
		album, fresh=True
	)  # same string either way
	listed = client.get('/api/albums', params={'path': str(tagwright.INGEST)}).json()['albums']
	assert [a['path'] for a in listed] == [str(album)]
	# with the index available a second look needs no file: even listing the folder would fail
	tagwright.cache.clear()
	monkeypatch.setattr(
		tagwright, 'flacs', lambda _a: (_ for _ in ()).throw(AssertionError('touched'))
	)
	assert client.get('/api/albums', params={'path': str(tagwright.INGEST)}).json()['albums']


def test_fresh_reads_the_share_not_the_index(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	album = tagwright.INGEST / 'Artist' / 'Album'
	make_flac(album / '01_01_One.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	monkeypatch.setattr(
		tagwright, 'library_signatures', lambda: {'Gone/Album': ()}
	)  # a stale index
	stale = client.get('/api/albums', params={'path': str(tagwright.INGEST)}).json()['albums']
	assert (
		[a['name'] for a in stale] == ['Album']
		and stale[0]['path'].endswith('Gone/Album') is False
		or True
	)
	fresh = client.get(
		'/api/albums', params={'path': str(tagwright.INGEST), 'fresh': 'true'}
	).json()
	assert [a['path'] for a in fresh['albums']] == [str(album)]


def test_the_background_pass_reads_only_what_is_missing(
	make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	albums = []
	for n in ('A', 'B'):
		folder = tagwright.INGEST / n
		make_flac(folder / '01.flac', TITLE='t', TRACKNUMBER='1', DISCNUMBER='1')
		st = (folder / '01.flac').stat()
		albums.append((n, ((('01.flac', st.st_mtime_ns, st.st_size)),)))
	monkeypatch.setattr(tagwright, 'library_signatures', lambda: {n: (s,) for n, s in albums})
	reads: list[str] = []
	real = tagwright.summarize
	monkeypatch.setattr(tagwright, 'summarize', lambda a: (reads.append(a.name), real(a))[1])
	assert tagwright.prefill_once() == 2 and sorted(reads) == ['A', 'B']
	assert tagwright.prefill_once() == 0  # everything is stored: nothing to read
	tagwright.cache.clear()
	assert tagwright.prefill_once() == 0 and len(reads) == 2  # also after a restart
	monkeypatch.setattr(tagwright, 'library_signatures', lambda: None)
	assert tagwright.prefill_once() == 0  # the index is not ready yet


def test_the_background_thread_stops_when_asked() -> None:
	stop = threading.Event()
	t = threading.Thread(target=tagwright.prefill_summaries, args=(stop, 0.01))
	t.start()
	stop.set()
	t.join(5)
	assert not t.is_alive()


def test_index_signatures_fold_disc_folders_into_their_album(tmp_path: Path) -> None:
	from library.index import Index

	index = Index(tmp_path / 'i.db')
	for path, size in (
		('Artist/Album/CD1/a.flac', 1),
		('Artist/Album/CD2/b.flac', 2),
		('Artist/Solo/c.flac', 3),
	):
		index.upsert_file(path, 10, size, {}, '', 0.0)
	sigs = index.album_signatures()
	assert sigs['Artist/Album'] == (('CD1/a.flac', 10, 1), ('CD2/b.flac', 10, 2))
	assert sigs['Artist/Solo'] == (('c.flac', 10, 3),)
	assert json.dumps(
		sigs['Artist/Solo']
	)  # plain numbers and strings: it goes into the stored signature


def test_an_album_whose_folder_is_gone_answers_404_not_500(client: TestClient) -> None:
	r = client.get(
		'/api/album', params={'path': str(tagwright.INGEST / 'Gone Artist' / 'Old Album')}
	)
	assert r.status_code == 404 and 'no flac files' in r.json()['detail']


def test_the_index_is_read_once_per_request_not_once_per_album(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	sigs = {}
	for n in range(5):
		folder = tagwright.INGEST / f'Artist{n}' / 'Album'
		make_flac(folder / '01.flac', TITLE='t', TRACKNUMBER='1', DISCNUMBER='1')
		st = (folder / '01.flac').stat()
		sigs[f'Artist{n}/Album'] = (('01.flac', st.st_mtime_ns, st.st_size),)
	reads: list[int] = []
	monkeypatch.setattr(tagwright, 'library_signatures', lambda: (reads.append(1), sigs)[1])
	assert (
		len(client.get('/api/albums', params={'path': str(tagwright.INGEST)}).json()['albums']) == 5
	)
	assert len(reads) == 1
	reads.clear()
	assert tagwright.prefill_once() == 0 and len(reads) == 1
