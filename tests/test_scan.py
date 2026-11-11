"""Finding albums and keeping every path inside ROOT (ADR 0006, 0007)."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as tagwright

from .conftest import MakeFlac


def test_disc_folders_belong_to_their_parent_album(make_flac: MakeFlac) -> None:
	root = tagwright.ROOT
	make_flac(root / 'Box' / 'Disc 1' / 'a.flac')
	make_flac(root / 'Box' / 'CD2' / 'b.flac')
	make_flac(root / 'Single' / 'c.flac')
	assert tagwright.album_dirs(root) == [root / 'Box', root / 'Single']


def test_root_itself_is_never_an_album(make_flac: MakeFlac) -> None:
	make_flac(tagwright.ROOT / 'Single' / 'c.flac')
	assert tagwright.ROOT not in tagwright.album_dirs(tagwright.ROOT)


def test_flacs_are_sorted_and_recursive(make_flac: MakeFlac) -> None:
	folder = tagwright.ROOT / 'Box'
	make_flac(folder / 'Disc 2' / '01.flac')
	make_flac(folder / 'Disc 1' / '02.flac')
	assert [f.parent.name for f in tagwright.flacs(folder)] == ['Disc 1', 'Disc 2']


def test_safe_accepts_paths_under_root() -> None:
	assert tagwright.safe(str(tagwright.ROOT / 'x')) == tagwright.ROOT / 'x'
	assert tagwright.safe(str(tagwright.ROOT)) == tagwright.ROOT


@pytest.mark.parametrize('bad', ['/etc', '..', '/', 'x/../../..'])
def test_safe_rejects_paths_outside_root(bad: str, tmp_path: Path) -> None:
	with pytest.raises(HTTPException) as err:
		tagwright.safe(str(tmp_path / bad) if not bad.startswith('/') else bad)
	assert err.value.status_code == 400


def test_hidden_folders_and_files_are_not_albums_or_tracks(make_flac: MakeFlac) -> None:
	root = tagwright.ROOT
	make_flac(root / 'Real Album' / '01.flac')
	make_flac(root / 'Real Album' / '._01.flac')  # AppleDouble litter
	make_flac(
		root / '.slskd-incomplete' / 'user' / 'Half Album' / '01.flac'
	)  # a download in progress
	make_flac(root / 'Real Album' / '.cache' / '02.flac')
	assert tagwright.album_dirs(root) == [root / 'Real Album']
	assert tagwright.flacs(root / 'Real Album') == [root / 'Real Album' / '01.flac']


def test_a_dotted_root_is_still_scanned(make_flac: MakeFlac, tmp_path: Path) -> None:
	base = tmp_path / '.library'
	make_flac(base / 'A' / '01.flac')
	assert tagwright.album_dirs(base) == [base / 'A']


def test_the_board_does_not_list_hidden_folders(client: TestClient, make_flac: MakeFlac) -> None:
	make_flac(tagwright.ROOT / '.slskd-incomplete' / 'x' / '01.flac', TITLE='t')
	assert client.get('/api/albums').json()['albums'] == []


def test_a_disc_folder_directly_in_the_base_is_an_album_of_its_own_not_the_base(
	make_flac: MakeFlac,
) -> None:
	root = tagwright.ROOT
	make_flac(root / 'CD1' / '01.flac')
	make_flac(root / 'CD2' / '01.flac')
	make_flac(root / 'Real Album' / '01.flac')
	assert tagwright.album_dirs(root) == [root / 'CD1', root / 'CD2', root / 'Real Album']
	assert tagwright.flacs(root / 'CD1') == [root / 'CD1' / '01.flac']


def test_an_album_does_not_swallow_the_albums_in_its_other_subfolders(make_flac: MakeFlac) -> None:
	root = tagwright.ROOT
	make_flac(root / 'Outer' / '01.flac')
	make_flac(root / 'Outer' / 'Disc 2' / '01.flac')
	make_flac(root / 'Outer' / 'Inner Album' / '01.flac')  # another album below it
	assert tagwright.flacs(root / 'Outer') == [
		root / 'Outer' / '01.flac',
		root / 'Outer' / 'Disc 2' / '01.flac',
	]
	assert tagwright.album_dirs(root) == [root / 'Outer', root / 'Outer' / 'Inner Album']


def test_the_base_folder_is_never_listed_as_an_album(
	client: TestClient, make_flac: MakeFlac
) -> None:
	make_flac(tagwright.ROOT / 'CD1' / '01.flac', TITLE='t')
	make_flac(tagwright.ROOT / 'Other' / '01.flac', TITLE='u')
	paths = {a['path'] for a in client.get('/api/albums').json()['albums']}
	assert str(tagwright.ROOT) not in paths
	assert paths == {str(tagwright.ROOT / 'CD1'), str(tagwright.ROOT / 'Other')}
