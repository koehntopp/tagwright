"""MP3 files behind the Audio interface: ID3 frames read and written as Vorbis-style tags (ADR 0058, 0059)."""

import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from mutagen.id3 import ID3, TPOS, TRCK, TXXX, TYER
from PIL import Image

from pipeline import audio
from pipeline.mp3 import Mp3Audio
from pipeline.tagio import tag, upper_tags

from .conftest import MakeMp3


def reopen(path: Path) -> Mp3Audio:
	a = audio.open_audio(path)
	assert isinstance(a, Mp3Audio)
	return a


def tagged(path: Path, **tags: str | list[str]) -> Mp3Audio:
	a = reopen(path)
	a.add_tags()
	for k, v in tags.items():
		a[k] = v
	a.save()
	return reopen(path)


def test_the_usual_fields_are_text_frames_and_come_back(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	a = tagged(
		f,
		TITLE='One',
		ARTIST='Band',
		ALBUMARTIST='Band & Co',
		ALBUM='Album',
		DATE='2006-05-12',
		GENRE=['Rock', 'Pop'],
		COMPOSER='Me',
		DISCSUBTITLE='Live',
		MEDIA='CD',
	)
	assert a.tags['TITLE'] == ['One'] and a.tags['ALBUMARTIST'] == ['Band & Co']
	assert a.tags['DATE'] == ['2006-05-12']
	assert a.tags['GENRE'] == ['Rock', 'Pop']  # several values stay several values
	assert a.tags['DISCSUBTITLE'] == ['Live'] and a.tags['MEDIA'] == ['CD']
	id3 = ID3(f)
	assert id3.version[:2] == (2, 4) and id3['TIT2'].text == ['One']


def test_track_and_disc_numbers_are_the_halves_of_trck_and_tpos(
	tmp_path: Path, make_mp3: MakeMp3
) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	a = tagged(f, TRACKNUMBER='3', TRACKTOTAL='12', DISCNUMBER='2', TOTALDISCS='3')
	assert ID3(f)['TRCK'].text == ['3/12'] and ID3(f)['TPOS'].text == ['2/3']
	assert [a.tags[k] for k in ('TRACKNUMBER', 'TRACKTOTAL', 'TOTALTRACKS')] == [
		['3'],
		['12'],
		['12'],
	]
	assert a.tags['DISCTOTAL'] == ['3']
	a['TRACKNUMBER'] = '4'  # keeps the total
	assert a.tags['TRACKTOTAL'] == ['12']
	a['TRACKNUMBER'] = '5/9'  # a combined value is split
	assert (a.tags['TRACKNUMBER'], a.tags['TRACKTOTAL']) == (['5'], ['9'])
	del a['TRACKTOTAL']
	assert 'TRACKTOTAL' not in a.tags and a.tags['TRACKNUMBER'] == ['5']
	del a['TRACKNUMBER']
	assert 'TRACKNUMBER' not in a.tags


def test_every_other_key_is_a_txxx_frame_in_any_case(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	a = tagged(
		f,
		dynamic_range='8',
		**{'SET SUBTITLE': 'Disc one', 'ALBUM_COMPANY_PRESSED_BY': 'Pressing Plant'},
	)
	assert a.tags['DYNAMIC_RANGE'] == ['8'] and a.tags['dynamic_range'] == ['8']
	assert a.tags['SET SUBTITLE'] == ['Disc one']
	assert ID3(f)['TXXX:DYNAMIC_RANGE'].text == ['8']
	a['DYNAMIC_RANGE'] = '9'  # replaced, not duplicated
	assert len([x for x in a.tags.id3.getall('TXXX') if x.desc.upper() == 'DYNAMIC_RANGE']) == 1


def test_a_txxx_written_by_another_tool_is_a_key(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	id3 = ID3()
	id3.add(TXXX(encoding=3, desc='MusicBrainz Album Id', text=['abc']))
	id3.add(
		TXXX(encoding=3, desc='replaygain_album_gain', text=['-6.0 dB'])
	)  # how rsgain may spell it
	id3.save(f)
	a = reopen(f)
	assert a.tags['MUSICBRAINZ ALBUM ID'] == ['abc'] and a.tags['REPLAYGAIN_ALBUM_GAIN'] == [
		'-6.0 dB'
	]
	assert upper_tags(a)['MUSICBRAINZ ALBUM ID'] == ['abc']


def test_lyrics_and_comment_have_their_own_frames(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	text = '[00:01.00]line one\n[00:05.00]line two'
	a = tagged(f, LYRICS=text, COMMENT='ripped')
	assert a.tags['LYRICS'] == [text] and a.tags['COMMENT'] == ['ripped']
	assert ID3(f).getall('USLT')[0].text == text
	del a['LYRICS']
	assert 'LYRICS' not in a.tags
	a.save()
	assert 'LYRICS' not in reopen(f).tags and not ID3(f).getall('USLT')


def test_the_tag_view_behaves_like_a_dict_of_lists(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	a = reopen(f)
	assert a.tags is None or not a.tags  # no tags yet
	a.add_tags()
	assert not a.tags and 'TITLE' not in a.tags and a.tags.get('TITLE') is None
	a['TITLE'] = 'One'
	a['X_CUSTOM'] = ['a', 'b']
	assert sorted(a.tags.keys()) == ['title', 'x_custom'] and len(a.tags) == 2
	assert tag(a.tags, 'ARTIST', 'TITLE') == 'One'
	assert dict(a.tags.items())['x_custom'] == ['a', 'b']
	assert 'title' in a.tags and 'TITLE' in a
	for k in list(a.tags.keys()):
		del a.tags[k]
	assert len(a.tags) == 0


def test_an_empty_list_removes_the_tag_and_an_empty_string_is_kept_like_in_flac(
	tmp_path: Path, make_mp3: MakeMp3
) -> None:
	a = tagged(make_mp3(tmp_path / 'a.mp3'), TITLE='One', X_CUSTOM='y')
	a['TITLE'] = []
	a['X_CUSTOM'] = ''
	assert 'TITLE' not in a.tags
	assert a.tags['X_CUSTOM'] == ['']


def test_a_file_from_an_id3v23_tagger_is_read(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	id3 = ID3()
	id3.add(TYER(encoding=1, text=['2006']))
	id3.save(f, v2_version=3)
	assert ID3(f).version == (2, 3, 0)
	assert tag(reopen(f).tags, 'DATE') == '2006'


def png(size: tuple[int, int] = (30, 20)) -> bytes:
	buf = io.BytesIO()
	Image.new('RGB', size, 'red').save(buf, 'PNG')
	return buf.getvalue()


def test_covers_are_apic_frames_with_a_measured_size(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	a = reopen(f)
	assert a.pictures == []
	pic = audio.new_cover()
	pic.type, pic.mime, pic.data = 3, 'image/png', png()
	a.add_picture(pic)
	a.save()
	got = reopen(f).pictures
	assert len(got) == 1 and (got[0].type, got[0].mime, got[0].width, got[0].height) == (
		3,
		'image/png',
		30,
		20,
	)
	b = reopen(f)
	b.clear_pictures()
	b.save()
	assert reopen(f).pictures == []


def test_the_stream_facts_and_the_extension_dispatch(tmp_path: Path, make_mp3: MakeMp3) -> None:
	f = make_mp3(tmp_path / 'A.MP3')
	a = audio.open_audio(f)
	assert isinstance(a, Mp3Audio) and a.info.channels == 1 and 0.9 < a.info.length < 1.2
	assert a.info.sample_rate == 44100


def test_writing_before_add_tags_is_an_error_like_a_flac_without_tags(tmp_path: Path) -> None:
	f = tmp_path / 'bare.mp3'
	sf.write(f, np.zeros(44100, dtype='int16'), 44100, format='MP3')
	a = audio.open_audio(f)
	assert a.tags is None and a.pictures == []
	with pytest.raises(ValueError, match='add_tags'):
		a['TITLE'] = 'x'


def ffmpeg_style(path: Path) -> None:
	"""Frames as ffmpeg writes them from a FLAC: totals and some mapped keys as TXXX copies."""
	id3 = ID3(path)
	id3.add(TRCK(encoding=3, text=['1']))
	id3.add(TPOS(encoding=3, text=['1']))
	for desc, value in [
		('TRACKTOTAL', '4'),
		('TOTALTRACKS', '4'),
		('DISCTOTAL', '2'),
		('TOTALDISCS', '2'),
	]:
		id3.add(TXXX(encoding=3, desc=desc, text=[value]))
	for desc, value in [('LABEL', 'Mercury'), ('MEDIA', 'Vinyl'), ('COMMENT', 'note')]:
		id3.add(TXXX(encoding=3, desc=desc, text=[value]))
	id3.save(path)


def test_txxx_copies_of_mapped_keys_are_read_and_do_not_break_listing(
	tmp_path: Path, make_mp3: MakeMp3
) -> None:
	"""A TXXX:DISCTOTAL beside a TPOS without total made listing the tags raise KeyError('disctotal'), so the
	Discogs tags step failed on every such MP3 (ADR 0059: a TXXX description in any case is a key)."""
	f = make_mp3(tmp_path / 'a.mp3')
	ffmpeg_style(f)
	t = upper_tags(reopen(f))
	assert t['TRACKNUMBER'] == ['1'] and t['TRACKTOTAL'] == ['4'] and t['DISCTOTAL'] == ['2']
	assert t['LABEL'] == ['Mercury'] and t['MEDIA'] == ['Vinyl'] and t['COMMENT'] == ['note']


def test_writing_a_mapped_key_moves_its_txxx_copy_into_the_frame(
	tmp_path: Path, make_mp3: MakeMp3
) -> None:
	f = make_mp3(tmp_path / 'a.mp3')
	ffmpeg_style(f)
	tagged(f, TRACKNUMBER='2', DISCNUMBER='1', LABEL='Mercury', MEDIA='Vinyl', COMMENT='note')
	id3 = ID3(f)
	assert id3['TRCK'].text == ['2/4'] and id3['TPOS'].text == [
		'1/2'
	]  # the totals join the number frames
	assert id3['TPUB'].text == ['Mercury'] and id3['TMED'].text == ['Vinyl']
	assert [c.text for c in id3.getall('COMM')] == [['note']]
	assert not [x.desc for x in id3.getall('TXXX')]  # no copies left behind


def test_any_save_moves_txxx_copies_into_their_frames(tmp_path: Path, make_mp3: MakeMp3) -> None:
	"""The Discogs step rewrites only changed tags; the copies still end up in their frames (as the macOS port)."""
	f = make_mp3(tmp_path / 'a.mp3')
	ffmpeg_style(f)
	tagged(f, DYNAMIC_RANGE='08')
	id3 = ID3(f)
	assert id3['TRCK'].text == ['1/4'] and id3['TPUB'].text == ['Mercury']
	assert sorted(x.desc for x in id3.getall('TXXX')) == ['DYNAMIC_RANGE']
