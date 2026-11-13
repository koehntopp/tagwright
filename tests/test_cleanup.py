"""Deleting the folder an album left behind in the staging folder: the list, the setting and the safety checks (ADR 0072)."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as tagwright

from .conftest import COMPLETE, MakeFlac


@pytest.fixture
def leftover() -> Path:
	"""A staging folder from which the songs have been moved: a cover, a log, a hidden file and a subfolder remain."""
	folder = tagwright.ROOT / 'Artist - Album [FLAC]'
	(folder / 'Scans').mkdir(parents=True)
	(folder / 'cover.jpg').write_bytes(b'x' * 2048)
	(folder / 'rip.log').write_text('log line\n')
	(folder / '.hidden').write_bytes(b'h' * 10)
	(folder / 'Scans' / 'back.png').write_bytes(b'y' * 4096)
	return folder


def allow(monkeypatch: pytest.MonkeyPatch, on: bool = True) -> None:
	monkeypatch.setitem(tagwright.settings, 'delete_after_move', on)


def test_the_folder_list_has_every_file_with_its_size(client: TestClient, leftover: Path) -> None:
	r = client.get('/api/folder', params={'path': str(leftover)}).json()
	files = {f['path']: f['size'] for f in r['files']}
	assert files == {'.hidden': 10, 'Scans/back.png': 4096, 'cover.jpg': 2048, 'rip.log': 9}
	assert (r['count'], r['bytes'], r['dirs'], r['audio'], r['truncated']) == (4, 6163, 1, 0, False)
	assert r['name'] == leftover.name


def test_a_long_list_is_cut_but_counted(client: TestClient, leftover: Path) -> None:
	for n in range(310):
		(leftover / f'f{n:03d}.txt').write_text('a')
	r = client.get('/api/folder', params={'path': str(leftover)}).json()
	assert len(r['files']) == 300 and r['count'] == 314 and r['truncated'] is True


def test_the_list_counts_songs_still_in_the_folder(
	client: TestClient, leftover: Path, make_flac: MakeFlac
) -> None:
	make_flac(leftover / 'CD1' / '01.flac', TITLE='t')
	assert client.get('/api/folder', params={'path': str(leftover)}).json()['audio'] == 1


@pytest.mark.parametrize('where', ['staging root', 'library', 'missing'])
def test_only_folders_inside_the_staging_folder_can_be_listed_or_deleted(
	client: TestClient, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
	allow(monkeypatch)
	target = {
		'staging root': tagwright.ROOT,
		'library': tagwright.INGEST,
		'missing': tagwright.ROOT / 'nope',
	}[where]
	listed = client.get('/api/folder', params={'path': str(target)})
	deleted = client.post('/api/folder/delete', json={'path': str(target)})
	assert listed.status_code in (400, 404) and deleted.status_code in (400, 404)
	assert tagwright.ROOT.is_dir() and tagwright.INGEST.is_dir()


def test_a_folder_inside_the_library_is_refused(
	client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
	allow(monkeypatch)
	album = tagwright.INGEST / 'Artist' / 'Album'
	album.mkdir(parents=True)
	assert client.post('/api/folder/delete', json={'path': str(album)}).status_code == 400
	assert album.is_dir()


def test_deleting_needs_the_setting(client: TestClient, leftover: Path) -> None:
	r = client.post('/api/folder/delete', json={'path': str(leftover)})
	assert r.status_code == 409 and 'Settings' in r.json()['detail']
	assert leftover.is_dir()


def test_deleting_is_refused_while_a_job_runs(
	client: TestClient, leftover: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	allow(monkeypatch)
	monkeypatch.setitem(tagwright.job, 'state', 'running')
	assert client.post('/api/folder/delete', json={'path': str(leftover)}).status_code == 409
	assert leftover.is_dir()


def test_a_folder_that_still_holds_a_song_is_not_deleted(
	client: TestClient, leftover: Path, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	allow(monkeypatch)
	make_flac(leftover / 'Scans' / 'oops.flac', TITLE='t')
	r = client.post('/api/folder/delete', json={'path': str(leftover)})
	assert r.status_code == 409 and '1 song' in r.json()['detail']
	assert (leftover / 'cover.jpg').exists()


def test_the_leftover_folder_is_deleted_and_logged(
	client: TestClient,
	leftover: Path,
	monkeypatch: pytest.MonkeyPatch,
	caplog: pytest.LogCaptureFixture,
) -> None:
	allow(monkeypatch)
	other = tagwright.ROOT / 'Another album'
	other.mkdir()
	with caplog.at_level(logging.INFO, logger='app'):
		r = client.post('/api/folder/delete', json={'path': str(leftover)})
	assert r.json() == {'deleted': True, 'files': 4, 'bytes': 6163}
	assert not leftover.exists() and other.is_dir() and tagwright.ROOT.is_dir()
	assert 'deleted the folder Artist - Album [FLAC] (4 files, 6163 bytes)' in caplog.text


def test_the_setting_is_off_by_default_and_saved(client: TestClient) -> None:
	assert client.get('/api/settings').json()['delete_after_move'] is False
	body = {'input': str(tagwright.ROOT), 'output': str(tagwright.INGEST)}
	assert client.post('/api/settings', json={**body, 'delete_after_move': True}).json()[
		'delete_after_move'
	]
	assert tagwright.settings['delete_after_move'] is True
	assert (
		client.post('/api/settings', json=body).json()['delete_after_move'] is True
	)  # absent: unchanged
	assert not client.post('/api/settings', json={**body, 'delete_after_move': False}).json()[
		'delete_after_move'
	]


def test_the_move_dialog_text_follows_the_setting(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	album = tagwright.ROOT / 'Artist - Album'
	make_flac(album / '01_01_One.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1', **COMPLETE)
	off = client.get('/api/move/preview', params={'path': str(album)}).json()['stays']
	assert 'stay in the staging folder' in off
	allow(monkeypatch)
	on = client.get('/api/move/preview', params={'path': str(album)}).json()['stays']
	assert 'asked whether to delete' in on and 'stay in the staging folder' not in on


def test_empty_subfolders_are_listed_and_counted(client: TestClient) -> None:
	folder = tagwright.ROOT / 'elp'
	(folder / 'CD 1').mkdir(parents=True)
	(folder / 'CD 2' / 'Art').mkdir(parents=True)
	r = client.get('/api/folder', params={'path': str(folder)}).json()
	assert (r['count'], r['audio'], r['dirs']) == (0, 0, 3)
	assert r['folders'] == ['CD 1', 'CD 2', 'CD 2/Art']
