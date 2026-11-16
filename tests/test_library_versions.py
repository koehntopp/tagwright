"""The "In your library" box: other versions of the same Discogs master (ADR 0082)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as tagwright

from .conftest import COMPLETE, MakeFlac


def make_album(make_flac: MakeFlac, folder: Path, **tags: str) -> Path:
	make_flac(
		folder / '01_01_One.flac',
		TITLE='One',
		TRACKNUMBER='1',
		DISCNUMBER='1',
		**{**COMPLETE, **tags},
	)
	return folder


def stored(monkeypatch: pytest.MonkeyPatch, *albums: Path) -> None:
	"""The library as the watcher's index and the stored summaries would know it."""
	rels = {a.relative_to(tagwright.INGEST).as_posix(): () for a in albums}
	monkeypatch.setattr(tagwright, 'library_signatures', lambda: rels)
	for a in albums:
		tagwright.summaries.put(str(a), 'sig', tagwright.summarize(a))


def test_the_summary_carries_the_master_id(make_flac: MakeFlac) -> None:
	a = make_album(make_flac, tagwright.ROOT / 'A', DISCOGS_MASTER_ID='m55')
	assert tagwright.summarize(a)['master'] == '55'
	b = make_album(make_flac, tagwright.ROOT / 'B')
	assert tagwright.summarize(b)['master'] == ''


def test_other_library_versions_of_the_master_are_listed(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	mine = make_album(make_flac, tagwright.ROOT / 'Mine', DISCOGS_MASTER_ID='m55')
	v1 = make_album(
		make_flac,
		tagwright.INGEST / 'Artist' / 'V1',
		DISCOGS_MASTER_ID='m55',
		ALBUM='Hello',
		VERSION='1982 DR14 CD',
	)
	v2 = make_album(
		make_flac,
		tagwright.INGEST / 'Artist' / 'V2',
		DISCOGS_MASTER_ID='m55',
		ALBUM='Hello',
		VERSION='2016 DR09 CD',
	)
	other = make_album(make_flac, tagwright.INGEST / 'Artist' / 'Other', DISCOGS_MASTER_ID='m99')
	stored(monkeypatch, v1, v2, other)
	r = client.get('/api/library/versions', params={'path': str(mine)})
	assert r.status_code == 200, r.text
	assert r.json()['master'] == '55'
	assert [(v['album'], v['version']) for v in r.json()['versions']] == [
		('Hello', '1982 DR14 CD'),
		('Hello', '2016 DR09 CD'),
	]


def test_a_library_album_does_not_list_itself(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	v1 = make_album(make_flac, tagwright.INGEST / 'Artist' / 'V1', DISCOGS_MASTER_ID='m55')
	v2 = make_album(make_flac, tagwright.INGEST / 'Artist' / 'V2', DISCOGS_MASTER_ID='m55')
	stored(monkeypatch, v1, v2)
	r = client.get('/api/library/versions', params={'path': str(v1)})
	assert [v['path'] for v in r.json()['versions']] == [str(v2)]


def test_an_album_without_a_master_lists_nothing(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	mine = make_album(make_flac, tagwright.ROOT / 'Mine')
	v1 = make_album(make_flac, tagwright.INGEST / 'Artist' / 'V1')  # no master either: no match
	stored(monkeypatch, v1)
	r = client.get('/api/library/versions', params={'path': str(mine)})
	assert r.json() == {'master': '', 'versions': []}
