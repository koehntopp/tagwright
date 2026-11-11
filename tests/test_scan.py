"""Finding albums and keeping every path inside ROOT (ADR 0006, 0007)."""

from pathlib import Path

import pytest
from fastapi import HTTPException

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
