"""The library as CSV for other programs (ADR 0077)."""

import csv
import io

from fastapi.testclient import TestClient

import app as tagwright

from .conftest import COMPLETE, MakeFlac


def rows(client: TestClient, **params: str) -> list[dict[str, str]]:
	r = client.get('/api/library/albums.csv', params=params)
	assert r.status_code == 200 and r.headers['content-type'].startswith('text/csv')
	return list(csv.DictReader(io.StringIO(r.text)))


def library_album(make_flac: MakeFlac, artist: str = 'Test_Artist', **tags: str) -> None:
	folder = tagwright.INGEST / artist / 'Test_Album_2020_DR10_CD_TST_001'
	make_flac(
		folder / '01_01_One.flac',
		TITLE='One',
		TRACKNUMBER='1',
		DISCNUMBER='1',
		**{**COMPLETE, **tags},
	)


def test_the_header_is_the_albums_csv_of_the_discogs_repository(client: TestClient) -> None:
	head = client.get('/api/library/albums.csv').text.splitlines()[0]
	assert head == (
		'Album Artist,Album,Version,DR,Format,Edition,Original Title,Original Date,Release Date,'
		'Catalog Number,Discogs Release ID,MusicBrainz Album ID,Subtitle,Cover Art,_DIRECTORY_PATH,Directory'
	)


def test_one_row_per_library_album_with_its_tags(client: TestClient, make_flac: MakeFlac) -> None:
	library_album(
		make_flac, ORIGINALDATE='1999', ALBUM_EDITION='Deluxe', MUSICBRAINZ_ALBUMID='mb-1'
	)
	(row,) = rows(client)
	assert row['Album Artist'] == 'Test Artist' and row['Album'] == 'Test Album'
	assert (
		row['Version'] == '2020 DR10 CD (TST-001)' and row['DR'] == '10' and row['Format'] == 'CD'
	)
	assert row['Edition'] == 'Deluxe' and row['Original Date'] == '1999'
	assert row['Catalog Number'] == 'TST-001' and row['Discogs Release ID'] == '12345'
	assert row['MusicBrainz Album ID'] == 'mb-1'
	assert row['Cover Art'] == ''  # the fixture has no picture
	assert (
		row['_DIRECTORY_PATH']
		== row['Directory']
		== str(tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001')
	)


def test_the_album_title_follows_the_override_then_the_master_then_the_original_title(
	client: TestClient, make_flac: MakeFlac
) -> None:
	library_album(make_flac, ALBUM='Greatest [Remaster]')
	assert rows(client)[0]['Album'] == 'Greatest'
	library_album(make_flac, 'B', ALBUM_MASTER_TITLE='Master', ORIGINAL_TITLE='Orig')
	library_album(make_flac, 'C', ALBUM_TITLE_OVERRIDE='Mine', ALBUM_MASTER_TITLE='Master')
	assert [r['Album'] for r in rows(client)] == [
		'Master',
		'Mine',
		'Greatest',
	]  # by path: B, C, Test_Artist


def test_path_prefix_replaces_the_library_folder(client: TestClient, make_flac: MakeFlac) -> None:
	library_album(make_flac)
	(row,) = rows(client, path_prefix='/Volumes/flac/')
	assert row['Directory'] == '/Volumes/flac/Test_Artist/Test_Album_2020_DR10_CD_TST_001'
	assert row['_DIRECTORY_PATH'] == row['Directory']


def test_staging_albums_are_not_listed(client: TestClient, make_flac: MakeFlac) -> None:
	make_flac(tagwright.ROOT / 'Staged' / '01.flac', TITLE='x', **COMPLETE)
	assert rows(client) == []
