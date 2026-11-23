"""Track artists and credits from a Discogs release, one value per name; legacy tags; the required-tags guard
(ADR 0100)."""

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from pipeline import credits, fixtags

from .test_assign import REL

RELEASE = {
	'artists': [{'name': 'Band'}],
	'extraartists': [
		{'name': 'Wide Producer', 'role': 'Producer'},
		{'name': 'Range Mixer', 'role': 'Mixed By', 'tracks': '2'},
		{'name': 'Masterer', 'role': 'Mastered By'},
		{'name': 'Shooter', 'role': 'Photography By'},
	],
	'tracklist': [
		{
			'type_': 'track',
			'position': '1',
			'title': 'One',
			'artists': [{'name': 'X (3)', 'join': ','}, {'name': 'Y'}],
			'extraartists': [
				{'name': 'Writer (2)', 'role': 'Written-By, Producer [Co-producer]'},
				{'name': 'Poet', 'role': 'Lyrics By'},
				{'name': 'Player', 'role': 'Bass [Electric], Guitar'},
			],
		},
		{'type_': 'heading', 'title': 'Bonus Tracks'},
		{'type_': 'track', 'position': '2', 'title': 'Two'},
	],
}


def test_a_track_gets_its_own_credits_one_value_per_name() -> None:
	assert credits.track_tags(RELEASE, 0) == {
		'ARTIST': ['X', 'Y'],
		'COMPOSER': ['Writer'],
		'LYRICIST': ['Poet'],
		'PRODUCER': ['Writer'],  # the track's own producer wins over the release-wide one
		'PERSONNEL': [
			'Player - Bass',
			'Player - Guitar',
			'Masterer - Mastering Engineer',
			'Shooter - Photography',
		],
	}


def test_release_credits_follow_their_track_range_and_headings_are_not_tracks() -> None:
	tags = credits.track_tags(RELEASE, 1)
	assert tags['ARTIST'] == ['Band']  # no track artists: the release artists
	assert tags['PRODUCER'] == ['Wide Producer']
	assert tags['MIXER'] == ['Range Mixer']
	assert 'MIXER' not in credits.track_tags(RELEASE, 0)  # 'tracks': '2' does not cover track 1
	assert credits.track_tags(RELEASE, 2) == {}


def test_a_range_of_vinyl_positions() -> None:
	release = {
		'extraartists': [{'name': 'Arr', 'role': 'Arranged By', 'tracks': 'A2 to B1'}],
		'tracklist': [
			{'type_': 'track', 'position': p, 'title': p} for p in ('A1', 'A2', 'B1', 'B2')
		],
	}
	assert [credits.track_tags(release, i).get('ARRANGER') for i in range(4)] == [
		None,
		['Arr'],
		['Arr'],
		None,
	]


def test_joined_values_legacy_tags_and_the_required_guard() -> None:
	assert credits.split_joined(['A Adkins,G Kurstin; X']) == ['A Adkins', 'G Kurstin', 'X']
	assert credits.split_joined(['A', 'B']) == ['A', 'B']
	keys = [
		'PERFORMERYR',
		'Discogs Catalog Number-2',
		'_STATISTICS_TAGS',
		'DISCOGS_RELEASE_ID',
		'TITLE',
	]
	assert credits.legacy_keys(keys) == [
		'PERFORMERYR',
		'Discogs Catalog Number-2',
		'_STATISTICS_TAGS',
	]
	assert credits.lost_required({'TITLE': ['x'], 'ARTIST': ['']}, {'TITLE': [' ']}) == ['TITLE']


@pytest.fixture
def rel(monkeypatch: pytest.MonkeyPatch) -> dict:
	release = copy.deepcopy(REL)
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: release)
	monkeypatch.setitem(
		tagwright.raw_releases, '777', {'id': 777, 'title': 'New Release', 'year': 1987}
	)
	monkeypatch.setattr(tagwright, 'fix_album', lambda path, cfg: fixtags.FixResult(0))
	return release


def assign(client: TestClient, album: Path) -> dict:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/tracks/apply',
		json={
			'path': str(album),
			'release_id': '777',
			'import_titles': True,
			'assignments': [{'file': f, 'rel': i} for i, f in enumerate(files)],
		},
	)
	assert r.status_code == 200, r.text
	return r.json()


def test_the_assignment_writes_credits_per_name_and_drops_legacy_tags(
	client: TestClient, album: Path, rel: dict
) -> None:
	for t in rel['tracks']:
		t['credits'] = {'ARTIST': ['X', 'Y'], 'COMPOSER': ['A', 'B'], 'MIXER': ['M']}
	for f in album.glob('*.flac'):
		x = FLAC(f)
		x['COMPOSER'] = ['A,B']
		x['PERFORMERYR'] = ['A (vocal)']
		x['DISCOGS CATALOG NUMBER-2'] = ['Label: 1']
		x.save()
	assign(client, album)
	for f in album.glob('*.flac'):
		x = FLAC(f)
		assert x['ARTIST'] == ['X', 'Y']
		assert x['COMPOSER'] == ['A', 'B']
		assert x['MIXER'] == ['M']
		assert 'PERFORMERYR' not in x and 'DISCOGS CATALOG NUMBER-2' not in x


def test_an_assignment_that_would_empty_a_required_tag_is_not_saved(
	client: TestClient, album: Path, rel: dict
) -> None:
	rel['tracks'][0]['title'] = ''  # a broken release: the title would be emptied
	out = assign(client, album)
	first, second = sorted(album.glob('*.flac'))
	assert FLAC(first)['TITLE'] == ['One']
	assert FLAC(first)['DISCOGS_RELEASE_ID'] == ['12345']  # nothing of the assignment was saved
	assert any(f'{first.name}: not saved, it would lose TITLE' in line for line in out['log'])
	assert FLAC(second)['DISCOGS_RELEASE_ID'] == ['777']
