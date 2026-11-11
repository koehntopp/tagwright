"""The MusicBrainz consistency notes compare with the Discogs release itself (ADR 0023)."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright

MBID = '53dcfdab-7d3b-4068-bb90-67e347ebb8fb'


@pytest.fixture
def linked(album: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""An album whose files say Discogs 12345, year 2020 and MusicBrainz release MBID."""
	for f in tagwright.flacs(album):
		audio = FLAC(f)
		audio['MUSICBRAINZ_ALBUMID'] = [MBID]
		audio.save()
	monkeypatch.setattr(
		tagwright,
		'mb_release',
		lambda mbid: {'discogs_ids': ['12345'], 'year': '1987', 'tracks': []},
	)
	return album


def check(client: TestClient, album: Path) -> list[str]:
	return client.get('/api/musicbrainz/check', params={'path': str(album)}).json()['notes']


def test_the_year_is_the_discogs_releases_not_the_old_year_tags(
	client: TestClient, linked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# the files still say 2020 (the previous release); the release assigned now is from 1987, like MusicBrainz
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: {'year': 1987})
	assert check(client, linked) == []


def test_a_real_year_difference_is_still_noted(
	client: TestClient, linked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: {'year': 1980})
	assert check(client, linked) == ['Year: Discogs 1980, MusicBrainz 1987.']


def test_without_discogs_the_year_tags_are_used(
	client: TestClient, linked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	def down(rid: str) -> dict:
		raise HTTPException(502, 'Discogs: down')

	monkeypatch.setattr(tagwright, 'release_tracks', down)
	assert check(client, linked) == ['Year: Discogs 2020, MusicBrainz 1987.']


def test_a_discogs_link_to_another_release_is_noted(
	client: TestClient, linked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(tagwright, 'release_tracks', lambda rid: {'year': 1987})
	monkeypatch.setattr(
		tagwright,
		'mb_release',
		lambda mbid: {'discogs_ids': ['10612976'], 'year': '1987', 'tracks': []},
	)
	assert check(client, linked) == [
		'MusicBrainz links Discogs release 10612976, this album uses 12345.'
	]


def test_no_notes_without_both_ids(client: TestClient, album: Path) -> None:
	assert check(client, album) == []  # no MusicBrainz release
