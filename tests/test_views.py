"""Staging and Library views: both folders are reachable, names follow the layout, edits refresh the watcher (ADR 0038)."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from library.index import Index
from library.scanner import scan
from library.watcher import Library, Settings
from pipeline.naming import bliss_name

from .conftest import COMPLETE, MakeFlac


def library_album(make_flac: MakeFlac) -> Path:
	folder = tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001'
	for number, title in ((1, 'One'), (2, 'Two')):
		make_flac(
			folder / f'01_{number:02d}_{title}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**COMPLETE,
		)
	return folder


class TestBothFolders:
	def test_safe_accepts_the_staging_and_the_library_folder(self) -> None:
		assert tagwright.safe(str(tagwright.ROOT / 'a')) == tagwright.ROOT / 'a'
		assert tagwright.safe(str(tagwright.INGEST / 'a')) == tagwright.INGEST / 'a'
		assert tagwright.safe(str(tagwright.INGEST)) == tagwright.INGEST

	@pytest.mark.parametrize('bad', ['/etc', '/', '..'])
	def test_everything_else_is_refused(self, bad: str) -> None:
		with pytest.raises(Exception, match='400'):
			tagwright.safe(bad)

	def test_a_path_next_to_the_library_folder_is_refused(self) -> None:
		with pytest.raises(Exception, match='400'):
			tagwright.safe(str(tagwright.INGEST) + '_other/x')

	def test_the_board_lists_the_library_folder_like_the_staging_folder(
		self, client: TestClient, make_flac: MakeFlac
	) -> None:
		library_album(make_flac)
		r = client.get('/api/albums', params={'path': str(tagwright.INGEST)}).json()
		assert r['base'] == str(tagwright.INGEST)
		assert [(a['status'], a['tracks']) for a in r['albums']] == [('fixed', 2)]
		assert client.get('/api/albums').json()['albums'] == []  # the default is still staging

	def test_a_library_album_can_be_opened_and_edited(
		self, client: TestClient, make_flac: MakeFlac
	) -> None:
		folder = library_album(make_flac)
		assert client.get('/api/tags', params={'path': str(folder)}).status_code == 200
		r = client.post(
			'/api/overrides', json={'path': str(folder), 'artist': 'Other', 'title': ''}
		)
		assert r.status_code == 200

	def test_an_album_already_in_the_library_cannot_be_moved(
		self, client: TestClient, make_flac: MakeFlac
	) -> None:
		folder = library_album(make_flac)
		p = client.get('/api/move/preview', params={'path': str(folder)}).json()
		assert (p['can_move'], p['problems']) == (False, ['this album is already in the library'])
		assert client.post('/api/move', json={'path': str(folder)}).status_code == 409
		assert len(list(folder.glob('*.flac'))) == 2

	def test_in_library_tells_the_two_apart(self) -> None:
		assert tagwright.in_library(tagwright.INGEST / 'a')
		assert not tagwright.in_library(tagwright.ROOT / 'a')


class TestFileNames:
	def test_the_default_template_gives_the_bliss_name(self) -> None:
		t = {'TITLE': ['Hello World'], 'TRACKNUMBER': ['3/12'], 'DISCNUMBER': ['1/2']}
		assert tagwright.file_name(t) == bliss_name(t) == '01_03_Hello_World.flac'

	def test_a_missing_tag_gives_no_name(self) -> None:
		assert tagwright.file_name({'TITLE': ['x'], 'TRACKNUMBER': ['1']}) is None

	def test_the_filenames_step_follows_the_template(
		self, album: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		assert tagwright.summarize(album)['steps'][5]['done'] is True
		template = {
			'folders': [[{'tag': 'ALBUMARTIST'}]],
			'filename': [
				{'tag': 'TRACKNUMBER', 'fmt': 'num', 'pad': 2},
				{'text': ' '},
				{'tag': 'TITLE'},
			],
		}
		monkeypatch.setattr(tagwright, 'settings', {'library': {'template': template}})
		assert tagwright.summarize(album)['steps'][5]['done'] is False
		tagwright.rename_files(album, tagwright.file_name)
		assert sorted(f.name for f in album.glob('*.flac')) == ['01 One.flac', '02 Two.flac']
		assert tagwright.summarize(album)['steps'][5]['done'] is True


class TestRefresh:
	def clock_library(self, root: Path, tmp_path: Path) -> Library:
		return Library(lambda: root, tmp_path / 'l.db', lambda: Settings(apply=False))

	def test_a_tag_edited_in_place_is_noticed_after_refresh(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		root = tmp_path / 'lib'
		f = make_flac(root / 'A' / 'x.flac', TITLE='Old', ALBUMARTIST='A', ALBUM='B')
		lib = self.clock_library(root, tmp_path)
		lib.cycle()
		audio = FLAC(f)
		audio['TITLE'] = ['New']
		audio.save()
		os.utime(
			f, (f.stat().st_atime, f.stat().st_mtime + 5)
		)  # coarse timestamps must not hide the edit
		assert scan(root, lib._index, 1.0).read == 0  # a quiet pass does not look inside files
		lib.refresh(root / 'A')
		assert scan(root, lib._index, 2.0).read == 1
		assert lib._index.items()[0].tags['TITLE'] == 'New'

	def test_refresh_ignores_folders_outside_the_library(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		root = tmp_path / 'lib'
		make_flac(root / 'x.flac', TITLE='T', ALBUMARTIST='A', ALBUM='B')
		lib = self.clock_library(root, tmp_path)
		lib.cycle()
		lib.refresh(tmp_path / 'elsewhere')
		assert lib._index.dir_mtime('') is not None

	def test_refresh_before_the_first_pass_does_nothing(self, tmp_path: Path) -> None:
		self.clock_library(tmp_path, tmp_path).refresh(tmp_path)

	def test_a_write_in_a_library_album_refreshes_it(
		self, make_flac: MakeFlac, album: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		folder = library_album(make_flac)
		seen: list[Path] = []
		monkeypatch.setattr(tagwright.library, 'refresh', seen.append)
		tagwright.fresh_summary(folder)
		tagwright.fresh_summary(album)  # staging: not the watcher's business
		assert seen == [folder]

	def test_forget_tree_only_takes_the_folder_and_below(self) -> None:
		index = Index(':memory:')
		for d in ('a', 'a/b', 'a_b', 'c'):
			index.set_dir(d, 1)
		index.forget_tree('a')
		assert [d for d in ('a', 'a/b', 'a_b', 'c') if index.dir_mtime(d) == 1] == ['a_b', 'c']
		assert (
			index.dir_mtime('a/b') == -1
		)  # unknown, so it is listed again; the row stays for the scanner


def test_the_folders_are_not_settings(client: TestClient, tmp_path: Path) -> None:
	before = (tagwright.ROOT, tagwright.INGEST)
	r = client.post('/api/settings', json={'input': str(tmp_path), 'output': str(tmp_path)})
	assert r.status_code == 200
	assert (tagwright.ROOT, tagwright.INGEST) == before
	assert 'input' not in tagwright.settings and 'output' not in tagwright.settings


def test_mount_source_names_the_nfs_export_or_the_bind_mount_path(tmp_path: Path) -> None:
	info = tmp_path / 'mountinfo'
	info.write_text(
		'1 0 0:1 / / rw - overlay overlay rw\n'
		'2 1 0:2 / /staging rw - nfs :/volume1/staging rw,vers=3,addr=192.0.2.10,hard\n'
		'5 1 0:3 / /plain rw - nfs 10.0.0.5:/export rw,vers=3\n'
		'3 1 259:1 /srv/flac/ingest /flac/ingest rw - ext4 /dev/nvme0n1p2 rw\n'
		'4 1 259:1 /srv/with\\040space /data rw - ext4 /dev/nvme0n1p2 rw\n'
	)
	assert (
		tagwright.mount_source(Path('/staging/Artist/Album'), info)
		== '192.0.2.10:/volume1/staging'
	)
	assert tagwright.mount_source(Path('/plain'), info) == '10.0.0.5:/export'
	assert tagwright.mount_source(Path('/flac/ingest'), info) == '/srv/flac/ingest'
	assert tagwright.mount_source(Path('/data'), info) == '/srv/with space'
	assert tagwright.mount_source(Path('/elsewhere'), info) == ''  # only the overlay root: unknown
	assert tagwright.mount_source(Path('/staging'), tmp_path / 'missing') == ''


def test_the_summary_carries_the_catalog_number(album: Path) -> None:
	assert tagwright.summarize(album)['catalog'] == 'TST-001'


def test_the_page_itself_is_never_cached(client: TestClient) -> None:
	r = client.get('/')
	assert r.status_code == 200
	assert r.headers['cache-control'] == 'no-cache'


def test_the_summary_says_where_an_album_is_now(album: Path, make_flac: MakeFlac) -> None:
	assert (
		tagwright.summarize(album)['folder'] == 'Test Artist-Test Album'
	)  # below the staging folder
	assert (
		tagwright.summarize(library_album(make_flac))['folder']
		== 'Test_Artist/Test_Album_2020_DR10_CD_TST_001'
	)


class TestChannels:
	@pytest.mark.parametrize(
		('title', 'channels'),
		[
			('Song (5.1 Mix)', 6),
			('Song [7.1 Atmos mix]', 8),
			('Song - Mono', 1),
			('Song (Stereo Version)', 2),
			('Song', 0),
			('Monologue', 0),
			('Track 15.1', 0),
			('The 5.10 Blues', 0),
			('Song (5.1) (Stereo)', 6),
		],
	)
	def test_a_release_track_title_can_name_the_channels(self, title: str, channels: int) -> None:
		from pipeline.tagio import channels_from_title

		assert channels_from_title(title) == channels

	def test_every_file_row_carries_its_channel_count(
		self, client: TestClient, make_flac: MakeFlac, album: Path
	) -> None:
		import numpy as np
		import soundfile as sf

		surround = album / '01_03_Surround.flac'
		sf.write(surround, np.zeros((2205, 6), dtype='int16'), 44100, format='FLAC')
		audio = FLAC(surround)
		for k, v in {
			'TITLE': 'Surround',
			'TRACKNUMBER': '3',
			'DISCNUMBER': '1',
			**COMPLETE,
		}.items():
			audio[k] = [v]
		audio.save()
		s = client.get('/api/album', params={'path': str(album)}).json()
		assert {f['title']: f['channels'] for f in s['files']} == {
			'One': 1,
			'Two': 1,
			'Surround': 6,
		}
		tags = client.get('/api/tags', params={'path': str(album)}).json()
		assert {t['title']: t['channels'] for t in tags['tracks']} == {
			'One': 1,
			'Two': 1,
			'Surround': 6,
		}
		assert {f['title']: f['channels'] for f in tagwright.album_files(album)} == {
			'One': 1,
			'Two': 1,
			'Surround': 6,
		}


class TestUnreadableAlbum:
	def test_the_board_gets_a_complete_summary_for_an_album_that_cannot_be_read(
		self, client: TestClient, album: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		real = tagwright.get_summary

		def broken(a: Path) -> dict:
			if a == album:
				raise OSError(9, 'Bad file descriptor')
			return real(a)

		monkeypatch.setattr(tagwright, 'get_summary', broken)
		row = client.get('/api/albums').json()['albums'][0]
		assert row['status'] == 'needs'
		assert 'Bad file descriptor' in row['error']
		# every field the card and the inspector read is there, so the page does not crash on it
		for key in (
			'lyrics',
			'steps',
			'files',
			'issues',
			'missing',
			'cover',
			'folder',
			'artist',
			'dr',
			'tracks',
		):
			assert key in row
		assert row['lyrics'] == {'synced': 0, 'plain': 0, 'instrumental': 0, 'missing': 0}
		assert [s['name'] for s in row['steps']] == list(tagwright.MISSING_LABEL)
		assert row['issues'][0]['level'] == 'error'
		assert 'cannot be read' in row['issues'][0]['text']

	def test_a_readable_album_next_to_it_is_unaffected(
		self, client: TestClient, album: Path, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
	) -> None:
		other = tagwright.ROOT / 'Other'
		make_flac(other / '01.flac', TITLE='x')
		real = tagwright.get_summary
		monkeypatch.setattr(
			tagwright,
			'get_summary',
			lambda a: (_ for _ in ()).throw(OSError('boom')) if a == album else real(a),
		)
		rows = {r['name']: r for r in client.get('/api/albums').json()['albums']}
		assert rows[album.name]['error'] == 'boom'
		assert 'error' not in rows['Other']


def test_musicbrainz_search_puts_releases_linking_the_discogs_id_first(
	monkeypatch: pytest.MonkeyPatch, client: TestClient, album: Path
) -> None:
	brief = lambda i, t: {'id': i, 'title': t, 'artist-credit': [{'name': 'A'}], 'media': []}  # noqa: E731  # tiny test double
	monkeypatch.setattr(tagwright, 'release_tracks', lambda did: None)
	monkeypatch.setitem(tagwright.raw_releases, '12345', {'identifiers': [], 'labels': []})

	def fake(path: str, **params: str | int) -> dict:
		if path == '/url':
			assert params['resource'] == 'https://www.discogs.com/release/12345'
			return {'relations': [{'release': {'id': 'linked'}}]}
		if path == '/release/linked':
			return brief('linked', 'Linked')
		return {'releases': [brief('plain', 'Plain'), brief('linked', 'Linked')]}

	monkeypatch.setattr(tagwright, 'musicbrainz', fake)
	rows = client.get('/api/musicbrainz/search', params={'q': 'a b', 'path': str(album)}).json()
	assert [(r['id'], r['match']) for r in rows] == [('linked', 'Discogs ID'), ('plain', '')]
