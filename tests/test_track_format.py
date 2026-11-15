"""The track list's sample rate and bit depth (ADR 0015)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import app as tagwright

from .conftest import MakeMp3


@pytest.mark.parametrize(
	('rate', 'bits', 'expected'),
	[
		(44100, 16, '44.1/16'),
		(96000, 24, '96/24'),
		(192000, 24, '192/24'),
		(88200, 24, '88.2/24'),
		(44100, 0, '44.1'),  # MP3 has no bit depth: the rate alone
		(0, 16, ''),
	],
)
def test_rate_bits(rate: int, bits: int, expected: str) -> None:
	assert tagwright.rate_bits(SimpleNamespace(sample_rate=rate, bits_per_sample=bits)) == expected


def test_the_track_rows_carry_the_format(album: Path) -> None:
	rows = tagwright.summarize(album)['files']
	assert [r['format'] for r in rows] == ['44.1/16', '44.1/16']


def test_an_mp3_row_shows_the_rate_alone(make_mp3: MakeMp3) -> None:
	folder = tagwright.ROOT / 'Mp3 Album'
	make_mp3(folder / '01.mp3', TITLE='One', ALBUMARTIST='A', ALBUM='B')
	assert tagwright.summarize(folder)['files'][0]['format'] == '44.1'
