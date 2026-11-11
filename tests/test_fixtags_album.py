"""fix_album on synthetic albums with a fake Discogs: what lands in the files (ADR 0014, 0036)."""

import io
import logging
import os
from pathlib import Path

import pytest
from mutagen.flac import FLAC, Picture
from PIL import Image

from pipeline import covers, fixtags, musicbrainz
from pipeline.config import Config
from pipeline.http import ApiError

from .conftest import MakeFlac
from .test_fixtags_pure import FakeGet

RELEASE = {
	'id': 123,
	'title': 'Release Title',
	'year': 2020,
	'master_id': 9,
	'country': 'UK',
	'labels': [{'name': 'Island (2)', 'catno': 'CAT-1'}],
	'genres': ['Rock'],
	'companies': [{'entity_type_name': 'Pressed By', 'name': 'MPO'}],
}
ANSWERS: dict[str, dict | Exception] = {
	'/releases/123': RELEASE,
	'/masters/9': {'title': 'Master Title', 'main_release': 55},
	'/releases/55': {'year': 2001},
}


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
	return Config(data_dir=tmp_path / 'data')


def tags_of(path: Path) -> dict[str, list[str]]:
	return {k.upper(): list(v) for k, v in (FLAC(path).tags or {}).items()}


def album_of(make_flac: MakeFlac, root: Path, count: int = 2, **extra: str) -> list[Path]:
	base = {'DISCOGS_RELEASE_ID': '123', 'ALBUM_DR': '7', 'TITLE': 't', **extra}
	return [make_flac(root / f'{i:02d}.flac', **base) for i in range(1, count + 1)]


def test_writes_the_same_album_tags_to_every_file(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	files = album_of(make_flac, tmp_path / 'a', CATALOGNUMBER='CAT-1', ALBUM_FORMAT='CD')
	result = fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
	assert result.changed == 2
	assert (result.album_name, result.version) == ('Master Title', '2020 DR07 CD (CAT-1)')
	for f in files:
		t = tags_of(f)
		assert t['ALBUM'] == ['Master Title']
		assert t['VERSION'] == ['2020 DR07 CD (CAT-1)']
		assert t['DATE'] == ['2020']
		assert t['ORIGINALDATE'] == ['2001']  # the main release of the master
		assert t['ALBUM_RELEASE_COUNTRY'] == ['UK']
		assert t['ALBUM_RELEASE_LABEL'] == [
			'Island (2)'
		]  # as Discogs has it; the cleaned name is in LABELS
		assert t['ALBUM_RELEASE_LABELS'] == ['Island']
		assert t['ALBUM_COMPANY_PRESSED_BY'] == ['MPO']
		assert t['ALBUM_MAX_RESOLUTION'] == ['44.1kHz']
		assert t['TITLE'] == ['t']  # per-track tags are left alone
		assert 'ALBUMARTIST' not in t  # no override: untouched


def test_a_second_run_changes_nothing(make_flac: MakeFlac, cfg: Config, tmp_path: Path) -> None:
	files = album_of(make_flac, tmp_path / 'a')
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
	before = [(f.stat().st_mtime_ns, f.stat().st_size) for f in files]
	assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 0
	assert [(f.stat().st_mtime_ns, f.stat().st_size) for f in files] == before


def test_messages_tell_name_change_from_tag_update_from_no_change(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	album_of(make_flac, tmp_path / 'a', ALBUM='Old Name')
	with caplog.at_level(logging.INFO):
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert 'Album name changed to Master Title [2020 DR07 CD]' in caplog.text
		caplog.clear()
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert 'No changes required for Master Title [2020 DR07 CD]' in caplog.text
	album_of(make_flac, tmp_path / 'b', ALBUM='Master Title')
	with caplog.at_level(logging.INFO):
		caplog.clear()
		fixtags.fix_album(tmp_path / 'b', cfg, get=FakeGet(ANSWERS))
		assert 'Tags updated in' in caplog.text


@pytest.mark.parametrize(
	('files', 'tags', 'reason'),
	[
		({}, {}, 'no flac files'),
		({'a.flac': {}}, {}, 'no Discogs release ID'),
		({'a.flac': {'DISCOGS_RELEASE_ID': 'r123'}}, {}, 'no Discogs release ID'),
		({'a.flac': {'DISCOGS_RELEASE_ID': ''}}, {}, 'no Discogs release ID'),
	],
)
def test_albums_without_a_usable_release_id_are_skipped_without_a_request(
	files: dict[str, dict[str, str]],
	tags: dict,
	reason: str,
	make_flac: MakeFlac,
	cfg: Config,
	tmp_path: Path,
) -> None:
	for name, t in files.items():
		make_flac(tmp_path / 'a' / name, **t)
	(tmp_path / 'a').mkdir(exist_ok=True)
	get = FakeGet({})
	result = fixtags.fix_album(tmp_path / 'a', cfg, get=get)
	assert (result.changed, result.skipped) == (0, reason)
	assert get.calls == []


def test_the_release_id_is_read_from_the_first_file_only(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	make_flac(tmp_path / 'a' / '01.flac')  # no ID
	make_flac(tmp_path / 'a' / '02.flac', DISCOGS_RELEASE_ID='123')
	assert (
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet({})).skipped == 'no Discogs release ID'
	)


def test_an_unreadable_first_file_skips_the_album(
	cfg: Config, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	(tmp_path / 'a').mkdir()
	(tmp_path / 'a' / '01.flac').write_bytes(b'not a flac file')
	with caplog.at_level(logging.WARNING):
		result = fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet({}))
	assert result.skipped == 'unreadable first file'
	assert 'Skipping unreadable file' in caplog.text


def test_a_release_id_with_spaces_is_accepted(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	album_of(make_flac, tmp_path / 'a', DISCOGS_RELEASE_ID=' 123 ')
	assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 2


def test_a_failing_release_lookup_raises(make_flac: MakeFlac, cfg: Config, tmp_path: Path) -> None:
	album_of(make_flac, tmp_path / 'a')
	with pytest.raises(ApiError) as err:
		fixtags.fix_album(
			tmp_path / 'a', cfg, get=FakeGet({'/releases/123': ApiError(404, 'Discogs: not found')})
		)
	assert err.value.status == 404
	assert 'ALBUM' not in tags_of(tmp_path / 'a' / '01.flac')  # nothing was written


def test_without_a_master_the_release_title_and_year_are_used(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	album_of(make_flac, tmp_path / 'a')
	answers = {'/releases/123': {**RELEASE, 'master_id': 0}}
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(answers))
	t = tags_of(tmp_path / 'a' / '01.flac')
	assert (t['ALBUM'], t['ORIGINALDATE']) == (['Release Title'], ['2020'])


def test_a_master_that_fails_still_tags_the_album(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	album_of(make_flac, tmp_path / 'a')
	answers = {**ANSWERS, '/masters/9': ApiError(502, 'down')}
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(answers))
	assert tags_of(tmp_path / 'a' / '01.flac')['ALBUM'] == ['Release Title']


def test_the_overrides_are_applied(make_flac: MakeFlac, cfg: Config, tmp_path: Path) -> None:
	album_of(
		make_flac,
		tmp_path / 'a',
		ALBUM_TITLE_OVERRIDE='My Title',
		ALBUM_ARTIST_OVERRIDE='Me',
		ALBUMARTIST='Wrong',
	)
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
	for f in (tmp_path / 'a').glob('*.flac'):
		t = tags_of(f)
		assert (t['ALBUM'], t['ALBUMARTIST']) == (['My Title'], ['Me'])
		assert t['ALBUM_TITLE_OVERRIDE'] == ['My Title']  # the user's tags stay


def test_max_resolution_follows_the_highest_rate_in_the_album(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	make_flac(tmp_path / 'a' / '01.flac', DISCOGS_RELEASE_ID='123')
	make_flac(tmp_path / 'a' / '02.flac', rate=96000)
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
	assert tags_of(tmp_path / 'a' / '01.flac')['ALBUM_MAX_RESOLUTION'] == ['96kHz']
	assert tags_of(tmp_path / 'a' / '02.flac')['ALBUM_MAX_RESOLUTION'] == ['96kHz']


def test_multi_disc_albums_are_fixed_as_one(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path
) -> None:
	make_flac(tmp_path / 'a' / 'Disc 1' / '01.flac', DISCOGS_RELEASE_ID='123')
	make_flac(tmp_path / 'a' / 'Disc 2' / '01.flac')
	fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
	assert tags_of(tmp_path / 'a' / 'Disc 2' / '01.flac')['ALBUM'] == ['Master Title']


class TestStaleTags:
	def test_tags_without_a_value_on_discogs_are_removed(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(
			make_flac, tmp_path / 'a',
			ALBUM_EDITION='Old', ALBUM_RELEASE_NOTES='old notes', ALBUM_COMPANY_GONE='x', ALBUM_CREDIT_GONE='y',
			ALBUM_IDENT_GONE='z', ALBUM_RELEASE_COUNTRY='XX', ALBUM_RELEASE_LABEL='Gone',
		)  # fmt: skip
		answers = {**ANSWERS, '/releases/123': {'id': 123, 'title': 'T', 'year': 2020}}
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(answers))
		t = tags_of(tmp_path / 'a' / '01.flac')
		for gone in (
			'ALBUM_RELEASE_NOTES',
			'ALBUM_COMPANY_GONE',
			'ALBUM_CREDIT_GONE',
			'ALBUM_IDENT_GONE',
			'ALBUM_RELEASE_COUNTRY',
			'ALBUM_RELEASE_LABEL',
		):
			assert gone not in t
		assert t['ALBUM_EDITION'] == ['Old']  # the user's edition is a value, not stale

	def test_edition_and_dr_are_removed_only_when_they_are_gone_from_the_first_file(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		make_flac(tmp_path / 'a' / '01.flac', DISCOGS_RELEASE_ID='123')
		make_flac(tmp_path / 'a' / '02.flac', ALBUM_EDITION='Leftover', ALBUM_DR='05')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		t = tags_of(tmp_path / 'a' / '02.flac')
		assert 'ALBUM_EDITION' not in t
		assert 'ALBUM_DR' not in t

	def test_a_stale_tag_alone_triggers_a_rewrite(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(make_flac, tmp_path / 'a')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		f = FLAC(tmp_path / 'a' / '01.flac')
		f['ALBUM_COMPANY_OLD'] = ['x']
		f.save()
		assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 1
		assert 'ALBUM_COMPANY_OLD' not in tags_of(tmp_path / 'a' / '01.flac')

	def test_legacy_work_and_part_tags_are_removed(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(make_flac, tmp_path / 'a', WORK='w', PART='p')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		t = tags_of(tmp_path / 'a' / '01.flac')
		assert 'WORK' not in t
		assert 'PART' not in t


class TestDiscSubtitle:
	def test_comes_from_each_tracks_own_set_subtitle(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		make_flac(
			tmp_path / 'a' / '01.flac', DISCOGS_RELEASE_ID='123', **{'SET SUBTITLE': ' First Disc '}
		)
		make_flac(tmp_path / 'a' / '02.flac', **{'SET SUBTITLE': 'Second Disc'})
		make_flac(tmp_path / 'a' / '03.flac')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert tags_of(tmp_path / 'a' / '01.flac')['DISCSUBTITLE'] == ['First Disc']
		assert tags_of(tmp_path / 'a' / '02.flac')['DISCSUBTITLE'] == ['Second Disc']
		assert 'DISCSUBTITLE' not in tags_of(tmp_path / 'a' / '03.flac')

	def test_is_removed_when_the_set_subtitle_is_gone(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(make_flac, tmp_path / 'a', DISCSUBTITLE='Old Disc')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert 'DISCSUBTITLE' not in tags_of(tmp_path / 'a' / '01.flac')

	def test_a_changed_set_subtitle_alone_triggers_a_rewrite(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(make_flac, tmp_path / 'a', **{'SET SUBTITLE': 'One'})
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		f = FLAC(tmp_path / 'a' / '01.flac')
		f['SET SUBTITLE'] = ['Two']
		f.save()
		assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 1
		assert tags_of(tmp_path / 'a' / '01.flac')['DISCSUBTITLE'] == ['Two']


class TestLanguages:
	MB = {'tracks': [{'id': 'x', 'disc': 1, 'position': 1, 'title': 't', 'languages': ['eng']}]}

	def test_lyrics_language_is_written_from_musicbrainz(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		monkeypatch.setattr(musicbrainz, 'release_languages', lambda *a: self.MB)
		album_of(
			make_flac,
			tmp_path / 'a',
			count=1,
			MUSICBRAINZ_ALBUMID='mbid',
			TRACKNUMBER='1',
			DISCNUMBER='1',
		)
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert tags_of(tmp_path / 'a' / '01.flac')['LYRICS_LANGUAGE'] == ['eng']

	def test_a_language_change_alone_triggers_a_rewrite(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		album_of(
			make_flac,
			tmp_path / 'a',
			count=1,
			MUSICBRAINZ_ALBUMID='mbid',
			TRACKNUMBER='1',
			DISCNUMBER='1',
		)
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		monkeypatch.setattr(musicbrainz, 'release_languages', lambda *a: self.MB)
		assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 1

	def test_without_a_musicbrainz_id_language_tags_are_not_touched(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		album_of(make_flac, tmp_path / 'a', count=1, LYRICS_LANGUAGE='spa')
		fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert tags_of(tmp_path / 'a' / '01.flac')['LYRICS_LANGUAGE'] == ['spa']


def picture(width: int, height: int, fmt: str = 'JPEG', mode: str = 'RGB') -> Picture:
	buf = io.BytesIO()
	Image.new(mode, (width, height), 'red').save(buf, format=fmt)
	pic = Picture()
	pic.mime = f'image/{fmt.lower()}'
	pic.type = 3
	pic.desc = 'front'
	pic.width, pic.height, pic.depth = width, height, 24
	pic.data = buf.getvalue()
	return pic


def embed(path: Path, *pics: Picture) -> None:
	audio = FLAC(path)
	for pic in pics:
		audio.add_picture(pic)
	audio.save()


class TestCovers:
	def test_a_large_cover_is_resized_to_the_limit_as_jpeg(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = make_flac(tmp_path / 'a' / '01.flac')
		embed(f, picture(3000, 2000))
		assert covers.resize_covers(tmp_path / 'a', 1500) == 1
		pic = FLAC(f).pictures[0]
		assert (pic.width, pic.height) == (1500, 1000)
		assert pic.mime == 'image/jpeg'
		assert (pic.type, pic.desc) == (3, 'front')
		assert Image.open(io.BytesIO(pic.data)).size == (1500, 1000)

	def test_a_cover_within_the_limit_is_left_alone(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = make_flac(tmp_path / 'a' / '01.flac')
		embed(f, picture(1500, 1500))
		before = f.read_bytes()
		assert covers.resize_covers(tmp_path / 'a', 1500) == 0
		assert f.read_bytes() == before

	def test_a_png_with_transparency_is_converted(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = make_flac(tmp_path / 'a' / '01.flac')
		embed(f, picture(2000, 2000, 'PNG', 'RGBA'))
		assert covers.resize_covers(tmp_path / 'a', 1500) == 1
		assert FLAC(f).pictures[0].mime == 'image/jpeg'

	def test_other_mime_types_tiny_and_corrupt_pictures_are_kept(
		self, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		f = make_flac(tmp_path / 'a' / '01.flac')
		gif, tiny, corrupt = picture(10, 10), picture(10, 10), picture(10, 10)
		gif.mime = 'image/gif'
		tiny.data = b'x' * 50
		corrupt.data = b'not an image at all' * 20
		embed(f, gif, tiny, corrupt)
		with caplog.at_level(logging.WARNING):
			assert covers.resize_covers(tmp_path / 'a', 5) == 0
		assert 'Corrupt or unparseable embedded image' in caplog.text
		assert len(FLAC(f).pictures) == 3

	def test_only_the_oversized_picture_of_several_is_replaced(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = make_flac(tmp_path / 'a' / '01.flac')
		small, big = picture(100, 100), picture(2000, 2000)
		big.type = 4
		embed(f, small, big)
		covers.resize_covers(tmp_path / 'a', 1500)
		pics = FLAC(f).pictures
		assert [(p.type, p.width) for p in pics] == [(3, 100), (4, 1500)]

	def test_files_without_pictures_are_skipped(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		make_flac(tmp_path / 'a' / '01.flac')
		assert covers.resize_covers(tmp_path / 'a', 1500) == 0

	def test_fix_album_resizes_the_cover_after_the_tags(
		self, make_flac: MakeFlac, cfg: Config, tmp_path: Path
	) -> None:
		files = album_of(make_flac, tmp_path / 'a', count=1)
		embed(files[0], picture(2000, 2000))
		fixtags.fix_album(
			tmp_path / 'a', Config(cfg.data_dir, cover_max_size=500), get=FakeGet(ANSWERS)
		)
		assert FLAC(files[0]).pictures[0].width == 500
		assert tags_of(files[0])['ALBUM'] == ['Master Title']


def test_files_that_vanish_are_skipped(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	files = album_of(make_flac, tmp_path / 'a')
	real = Path.is_file
	monkeypatch.setattr(Path, 'is_file', lambda self: False if self == files[1] else real(self))
	assert fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS)).changed == 1
	assert 'ALBUM' not in tags_of(files[1])


def test_an_unwritable_file_is_skipped_with_a_warning(
	make_flac: MakeFlac, cfg: Config, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	files = album_of(make_flac, tmp_path / 'a')
	files[1].chmod(0o444)
	try:
		if os.access(files[1], os.W_OK):
			pytest.skip('running as a user that can write read-only files')
		with caplog.at_level(logging.WARNING):
			result = fixtags.fix_album(tmp_path / 'a', cfg, get=FakeGet(ANSWERS))
		assert result.changed == 1
		assert 'Skipping unreadable or unwritable file' in caplog.text
	finally:
		files[1].chmod(0o644)
