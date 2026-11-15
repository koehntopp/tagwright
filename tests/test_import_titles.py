"""The "import song titles" checkbox of the Discogs and MusicBrainz dialogs (ADR 0078, 0013, 0023)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright

from .test_assign import REL, apply

MB_ID = '11111111-1111-1111-1111-111111111111'
MB = {
	'id': MB_ID,
	'artist': 'Test Artist',
	'name': 'MB Release',
	'artists': [{'id': 'a1', 'name': 'Test Artist'}],
	'group': {'id': '', 'title': '', 'type': '', 'first': ''},
	'barcode': '',
	'asin': '',
	'country': '',
	'status': '',
	'types': '',
	'disambiguation': '',
	'tracks': [
		{
			'i': i,
			'disc': 1,
			'track': i + 1,
			'part_of': '',
			'position': str(i + 1),
			'title': title,
			'duration': 0,
			'channels': 0,
			'artist': 'Test Artist',
			'artists': [{'id': 'a1', 'name': 'Test Artist'}],
		}
		for i, title in enumerate(['Uno', 'Dos'])
	],
}


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: REL)
	monkeypatch.setitem(
		tagwright.raw_releases, '777', {'id': 777, 'title': 'New Release', 'year': 1987}
	)


@pytest.fixture
def mb(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setitem(tagwright.mb_releases, MB_ID, MB)


def titles(album: Path) -> list[str]:
	return [FLAC(f)['TITLE'][0] for f in sorted(album.glob('*.flac'))]


def mb_apply(client: TestClient, album: Path, **extra: object) -> dict:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/musicbrainz/apply',
		json={
			'path': str(album),
			'id': MB_ID,
			'assignments': [{'file': f, 'rel': i} for i, f in enumerate(files)],
			**extra,
		},
	)
	assert r.status_code == 200, r.text
	return r.json()


def test_defaults_are_discogs_on_and_musicbrainz_off() -> None:
	assert tagwright.import_titles('discogs') is True
	assert tagwright.import_titles('musicbrainz') is False


def test_discogs_writes_titles_by_default(client: TestClient, album: Path, stubbed: None) -> None:
	REL['tracks'][0]['title'] = 'Eins'
	try:
		apply(client, album)
	finally:
		REL['tracks'][0]['title'] = 'One'
	assert 'Eins' in titles(album)


def test_discogs_keeps_titles_when_the_box_is_off(
	client: TestClient, album: Path, stubbed: None
) -> None:
	REL['tracks'][0]['title'] = 'Eins'
	try:
		files = [f.name for f in tagwright.flacs(album)]
		r = client.post(
			'/api/tracks/apply',
			json={
				'path': str(album),
				'release_id': '777',
				'import_titles': False,
				'assignments': [{'file': f, 'rel': i} for i, f in enumerate(files)],
			},
		)
		assert r.status_code == 200, r.text
	finally:
		REL['tracks'][0]['title'] = 'One'
	assert sorted(titles(album)) == ['One', 'Two']
	assert tagwright.import_titles('discogs') is False  # remembered


def test_musicbrainz_keeps_titles_by_default_and_numbers_the_files(
	client: TestClient, album: Path, mb: None
) -> None:
	out = mb_apply(client, album)
	assert sorted(titles(album)) == ['One', 'Two']
	tags = {k.upper(): list(v) for k, v in FLAC(sorted(album.glob('*.flac'))[0]).tags.items()}
	assert tags['MUSICBRAINZ_ALBUMID'] == [MB_ID]
	assert tags['MUSICBRAINZ_ARTISTID'] == ['a1']
	assert tags['TRACKNUMBER'] == ['1']
	assert any('album data only' in x for x in out['log'])


def test_the_box_off_keeps_track_and_disc_numbers_too(
	client: TestClient, album: Path, mb: None
) -> None:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/musicbrainz/apply',
		json={
			'path': str(album),
			'id': MB_ID,
			'assignments': [
				{'file': f, 'rel': i, 'disc': 3, 'track': 9} for i, f in enumerate(files)
			],
		},
	)
	assert r.status_code == 200, r.text
	tags = {k.upper(): list(v) for k, v in FLAC(sorted(album.glob('*.flac'))[0]).tags.items()}
	assert tags['TRACKNUMBER'] == ['1']
	assert tags['DISCNUMBER'] == ['1']
	assert tags['MUSICBRAINZ_ALBUMID'] == [MB_ID]  # album data is still written


def test_musicbrainz_writes_titles_when_the_box_is_on_and_remembers_it(
	client: TestClient, album: Path, mb: None
) -> None:
	mb_apply(client, album, import_titles=True)
	assert sorted(titles(album)) == ['Dos', 'Uno']
	tags = {k.upper(): list(v) for k, v in FLAC(sorted(album.glob('*.flac'))[0]).tags.items()}
	assert tags['TRACKNUMBER'] == ['1']
	assert tagwright.import_titles('musicbrainz') is True
	assert tagwright.import_titles('discogs') is True  # separate flags


def test_the_propose_endpoint_serves_musicbrainz_and_the_saved_flag(
	client: TestClient, album: Path, mb: None
) -> None:
	r = client.post(
		'/api/tracks/propose',
		json={'path': str(album), 'release_id': MB_ID, 'source': 'musicbrainz'},
	)
	assert r.status_code == 200, r.text
	d = r.json()
	assert d['import_titles'] is False
	assert len(d['release']['tracks']) == 2
	assert [f['rel'] for f in d['files']] == [0, 1]  # matched by disc and track number


def test_subtitles_are_written_with_the_box_on_only_and_keep_mine_skips_them(
	client: TestClient, album: Path, mb: None
) -> None:
	for t in MB['tracks']:
		t['subtitle'] = 'Reckless 40th'
	try:
		mb_apply(client, album)
		assert 'SET SUBTITLE' not in FLAC(sorted(album.glob('*.flac'))[0])
		files = [f.name for f in tagwright.flacs(album)]
		r = client.post(
			'/api/musicbrainz/apply',
			json={
				'path': str(album),
				'id': MB_ID,
				'import_titles': True,
				'assignments': [
					{'file': files[0], 'rel': 0},  # no key: the release track's own subtitle
					{'file': files[1], 'rel': 1, 'subtitle': None},  # Keep mine
				],
			},
		)
		assert r.status_code == 200, r.text
	finally:
		for t in MB['tracks']:
			t.pop('subtitle', None)
	first, second = (FLAC(f) for f in sorted(album.glob('*.flac')))
	assert first['SET SUBTITLE'] == ['Reckless 40th'] and first['DISCSUBTITLE'] == ['Reckless 40th']
	assert 'SET SUBTITLE' not in second


def test_a_subtitle_typed_in_the_dialog_is_written_per_file(
	client: TestClient, album: Path, mb: None
) -> None:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/musicbrainz/apply',
		json={
			'path': str(album),
			'id': MB_ID,
			'import_titles': True,
			'assignments': [
				{'file': files[0], 'rel': 0, 'subtitle': 'Main set'},
				{'file': files[1], 'rel': 1, 'subtitle': ' Encore '},
			],
		},
	)
	assert r.status_code == 200, r.text
	got = [FLAC(f)['SET SUBTITLE'][0] for f in sorted(album.glob('*.flac'))]
	assert got == ['Main set', 'Encore']


def test_discogs_subtitles_start_at_every_heading_and_end_with_a_disc(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	raw = {
		'id': 6,
		'title': 'X',
		'artists': [{'name': 'A'}],
		'tracklist': [
			{'type_': 'heading', 'title': 'Reckless 40th Anniversary'},
			{'type_': 'track', 'position': 'CD1-1', 'title': 'One'},
			{'type_': 'track', 'position': 'CD1-2', 'title': 'Two'},
			{'type_': 'heading', 'title': 'Encore'},  # inside a disc: a new run
			{'type_': 'track', 'position': 'CD1-3', 'title': 'Three'},
			{'type_': 'heading', 'title': 'CD2 - 18 Til I Die'},
			{'type_': 'track', 'position': 'CD2-1', 'title': 'Four'},
			{
				'type_': 'track',
				'position': 'CD3-1',
				'title': 'Five',
			},  # a new disc without a heading
			{'type_': 'heading', 'title': 'CD4'},  # only the label: no subtitle
			{'type_': 'track', 'position': 'CD4-1', 'title': 'Six'},
		],
	}
	monkeypatch.setattr(tagwright, 'discogs', lambda path, **kw: raw)
	tagwright.releases.pop('6', None)
	got = [(t['title'], t['subtitle']) for t in tagwright.release_tracks('6')['tracks']]
	assert got == [
		('One', 'Reckless 40th Anniversary'),
		('Two', 'Reckless 40th Anniversary'),
		('Three', 'Encore'),
		('Four', '18 Til I Die'),
		('Five', ''),
		('Six', ''),
	]


def test_the_discogs_assignment_replaces_a_different_album_artist(
	client: TestClient, album: Path, stubbed: None
) -> None:
	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['ALBUMARTIST'] = ['Test and Artist']
		x.save()
	apply(client, album)
	assert {FLAC(f)['ALBUMARTIST'][0] for f in album.glob('*.flac')} == {'Test Artist'}


def test_an_album_artist_override_is_not_replaced(
	client: TestClient, album: Path, stubbed: None
) -> None:
	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['ALBUMARTIST'] = ['Mine']
		x['ALBUM_ARTIST_OVERRIDE'] = ['Mine']
		x.save()
	apply(client, album)
	assert {FLAC(f)['ALBUMARTIST'][0] for f in album.glob('*.flac')} == {'Mine'}


def test_a_title_typed_in_the_dialog_wins_over_the_release_title(
	client: TestClient, album: Path, mb: None
) -> None:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/musicbrainz/apply',
		json={
			'path': str(album),
			'id': MB_ID,
			'import_titles': True,
			'assignments': [
				{'file': files[0], 'rel': 0, 'title': '  Uno (fixed) '},
				{'file': files[1], 'rel': 1, 'title': ''},
			],
		},
	)
	assert r.status_code == 200, r.text
	assert sorted(titles(album)) == ['Dos', 'Uno (fixed)']


def test_the_artist_is_written_whenever_the_title_is(
	client: TestClient, album: Path, stubbed: None, mb: None
) -> None:
	def artists() -> set[str]:
		return {FLAC(f)['ARTIST'][0] for f in album.glob('*.flac')}

	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['ARTIST'] = ['Somebody Else']
		x.save()
	files = [f.name for f in tagwright.flacs(album)]
	off = {'path': str(album), 'release_id': '777', 'import_titles': False}
	assert (
		client.post(
			'/api/tracks/apply',
			json={**off, 'assignments': [{'file': f, 'rel': i} for i, f in enumerate(files)]},
		).status_code
		== 200
	)
	assert artists() == {'Somebody Else'}  # box off: an existing artist stays
	tagwright.settings['import_titles_discogs'] = True  # the box is remembered from the last apply
	apply(client, album)
	assert artists() == {'Test Artist'}
	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['ARTIST'] = ['Somebody Else']
		x.save()
	mb_apply(client, album, import_titles=True)
	assert artists() == {'Test Artist'}  # the MusicBrainz track artist


def test_discogs_leads_the_credits_and_an_empty_discogs_value_changes_nothing(
	client: TestClient, album: Path, stubbed: None
) -> None:
	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['COMPOSER'] = ['Old Composer']
		x.save()
	apply(client, album)  # REL's tracks name no composer: nothing to replace it with
	assert {FLAC(f)['COMPOSER'][0] for f in album.glob('*.flac')} == {'Old Composer'}
	for t in REL['tracks']:
		t['composers'] = ['New Composer']
	try:
		apply(client, album)
	finally:
		for t in REL['tracks']:
			t['composers'] = []
	assert {FLAC(f)['COMPOSER'][0] for f in album.glob('*.flac')} == {'New Composer'}
