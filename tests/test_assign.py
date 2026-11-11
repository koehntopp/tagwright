"""Assigning a Discogs release also refreshes the Discogs-owned tags at once (ADR 0013, 0043)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from pipeline import fixtags
from pipeline.http import ApiError

REL = {
	'id': '777',
	'title': 'New Release',
	'artist': 'Test Artist',
	'year': 1987,
	'catno': 'CAT-9',
	'master_id': 0,
	'image': '',
	'tracks': [
		{
			'i': 0,
			'position': '1',
			'disc': 1,
			'track': 1,
			'title': 'One',
			'duration': 10,
			'artist': 'Test Artist',
			'composers': [],
			'producers': [],
			'engineers': [],
		},
		{
			'i': 1,
			'position': '2',
			'disc': 1,
			'track': 2,
			'title': 'Two',
			'duration': 10,
			'artist': 'Test Artist',
			'composers': [],
			'producers': [],
			'engineers': [],
		},
	],
}


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: REL)
	monkeypatch.setitem(
		tagwright.raw_releases, '777', {'id': 777, 'title': 'New Release', 'year': 1987}
	)


def apply(client: TestClient, album: Path) -> dict:
	files = [f.name for f in tagwright.flacs(album)]
	r = client.post(
		'/api/tracks/apply',
		json={
			'path': str(album),
			'release_id': '777',
			'assignments': [{'file': f, 'rel': i} for i, f in enumerate(files)],
		},
	)
	assert r.status_code == 200, r.text
	return r.json()


def test_the_discogs_tags_step_runs_after_the_assignment(
	client: TestClient, album: Path, stubbed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
	seen: list[Path] = []

	def fake(path: Path, cfg: object) -> fixtags.FixResult:
		seen.append(path)
		return fixtags.FixResult(2, 'New Release', '1987 DR10 CD')

	monkeypatch.setattr(tagwright, 'fix_album', fake)
	out = apply(client, album)
	assert seen == [album]
	assert 'Discogs tags refreshed: New Release [1987 DR10 CD] (2 files changed)' in out['log']


def test_the_assignment_updates_the_year_through_the_real_step(
	client: TestClient, album: Path, stubbed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
	answers = {
		'/releases/777': {'id': 777, 'title': 'New Release', 'year': 1987, 'master_id': 0},
	}
	monkeypatch.setattr(fixtags.discogs, 'get', lambda path, **p: answers[path])
	monkeypatch.setattr(
		tagwright,
		'fix_album',
		lambda path, cfg: fixtags.fix_album(path, cfg, get=lambda p: answers[p]),
	)
	apply(client, album)
	tags = {k.upper(): list(v) for k, v in FLAC(sorted(album.glob('*.flac'))[0]).tags.items()}
	assert tags['DATE'] == ['1987']
	assert tags['DISCOGS_RELEASE_ID'] == ['777']
	assert tags['ALBUM'] == ['New Release']
	assert tagwright.summarize(album)['year'] == '1987'  # what the card shows


def test_a_discogs_failure_does_not_fail_the_assignment(
	client: TestClient, album: Path, stubbed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
	def down(path: Path, cfg: object) -> fixtags.FixResult:
		raise ApiError(429, 'Discogs rate limit reached; try again in a minute')

	monkeypatch.setattr(tagwright, 'fix_album', down)
	out = apply(client, album)
	assert any('not refreshed: Discogs rate limit' in line for line in out['log'])
	assert FLAC(sorted(album.glob('*.flac'))[0])['DISCOGS_RELEASE_ID'] == [
		'777'
	]  # the assignment itself is written
