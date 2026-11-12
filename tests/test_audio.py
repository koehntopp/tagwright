"""The audio seam (ADR 0058): which files count, and that opening goes through one place."""

from pathlib import Path

import pytest
from mutagen import MutagenError

from pipeline import audio

from .conftest import MakeFlac


@pytest.mark.parametrize(
	('name', 'expected'),
	[
		('a.flac', True),
		('A.FLAC', True),
		('a.mp3', True),
		('A.MP3', True),
		('cover.jpg', False),
		('flac', False),
		('a.ogg', False),
	],
)
def test_is_audio_goes_by_the_extension(name: str, expected: bool) -> None:
	assert audio.is_audio(name) is expected


def test_open_audio_reads_and_writes_tags(tmp_path: Path, make_flac: MakeFlac) -> None:
	f = make_flac(tmp_path / 'a.flac', TITLE='One')
	a = audio.open_audio(f)
	assert a.tags['TITLE'] == ['One'] and a.info.channels == 1
	a['TITLE'] = ['Two']
	a.save()
	assert audio.open_audio(f).tags['TITLE'] == ['Two']


def test_open_audio_raises_mutagens_error_for_a_damaged_file(tmp_path: Path) -> None:
	bad = tmp_path / 'bad.flac'
	bad.write_bytes(b'not a flac')
	with pytest.raises(MutagenError):
		audio.open_audio(bad)


def test_a_new_cover_can_be_embedded(tmp_path: Path, make_flac: MakeFlac) -> None:
	f = make_flac(tmp_path / 'a.flac')
	pic = audio.new_cover()
	pic.type, pic.mime, pic.data = 3, 'image/jpeg', b'\xff\xd8\xff'
	a = audio.open_audio(f)
	a.add_picture(pic)
	a.save()
	assert len(audio.open_audio(f).pictures) == 1
