"""Naming and lyrics rules that mirror the discogs scripts (ADR 0006, 0010)."""

from pathlib import Path

import pytest

import app as tagwright

from .conftest import MakeFlac


def test_clean_matches_the_bliss_rule() -> None:
	assert tagwright.clean('Beyoncé: Lemonade?') == 'Beyonce_Lemonade'
	assert tagwright.clean('AC/DC') == 'AC_DC'


def test_bliss_name_pads_disc_and_track() -> None:
	t = {'TITLE': ['Hello World'], 'TRACKNUMBER': ['3/12'], 'DISCNUMBER': ['1/2']}
	assert tagwright.bliss_name(t) == '01_03_Hello_World.flac'


@pytest.mark.parametrize('missing', ['TITLE', 'TRACKNUMBER', 'DISCNUMBER'])
def test_bliss_name_is_none_while_a_tag_is_empty(missing: str) -> None:
	t = {'TITLE': ['x'], 'TRACKNUMBER': ['1'], 'DISCNUMBER': ['1']}
	del t[missing]
	assert tagwright.bliss_name(t) is None


def test_bliss_album_appends_version_once() -> None:
	t = {'ALBUMARTIST': ['The Band'], 'ALBUM': ['Record'], 'VERSION': ['2020 DR10 CD']}
	assert tagwright.bliss_album(t) == 'The_Band/Record_2020_DR10_CD'
	t['ALBUM'] = ['Record 2020 DR10 CD']
	assert tagwright.bliss_album(t) == 'The_Band/Record_2020_DR10_CD'


def test_bliss_album_is_empty_without_album_artist() -> None:
	assert tagwright.bliss_album({'ALBUM': ['x'], 'ARTIST': ['y']}) == ''


@pytest.mark.parametrize(
	('tags', 'kind'),
	[
		({}, 'none'),
		({'LYRICS': ['']}, 'none'),
		({'LYRICS': [''], 'LYRICS_LANGUAGE': ['zxx']}, 'instr'),
		({'LYRICS': ['[instrumental:true]\n[00:00.00]']}, 'instr'),
		({'LYRICS': ['[00:01.00][Instrumental]']}, 'instr'),
		({'LYRICS': ['[00:01.00](instrumental)']}, 'instr'),
		({'LYRICS': ['[00:12.34]hello']}, 'lrc'),
		({'LYRICS': ['[0:12.3]not strict']}, 'txt'),
		({'LYRICS': ['just words']}, 'txt'),
	],
)
def test_lyric_kind_order(tags: dict[str, list[str]], kind: str) -> None:
	assert tagwright.lyric_kind(tags) == kind


def test_rename_files_uses_the_bliss_name(tmp_path: Path, make_flac: MakeFlac) -> None:
	folder = tagwright.ROOT / 'album'
	f = make_flac(folder / 'track.flac', TITLE='Hello', TRACKNUMBER='2', DISCNUMBER='1')
	log = tagwright.rename_files(folder)
	assert (folder / '01_02_Hello.flac').is_file()
	assert not f.exists()
	assert log


def test_rename_files_leaves_unready_files_alone(make_flac: MakeFlac) -> None:
	folder = tagwright.ROOT / 'album'
	f = make_flac(folder / 'track.flac', TITLE='Hello')  # no track or disc number
	tagwright.rename_files(folder)
	assert f.is_file()
