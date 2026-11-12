"""Whole albums of MP3 (and mixed) files through the program: status, Discogs tags, names, moves, editor (ADR 0059)."""

from pathlib import Path, PurePosixPath

import pytest
from fastapi.testclient import TestClient

import app as tagwright
from library import planner
from library.template import default
from pipeline import audio, fixtags
from pipeline.config import Config
from pipeline.naming import rename_files

from .conftest import COMPLETE, MakeFlac, MakeMp3
from .test_fixtags_album import ANSWERS
from .test_fixtags_pure import FakeGet


def mp3_album(make_mp3: MakeMp3, folder: Path) -> list[Path]:
	return [
		make_mp3(
			folder / f'01_{n:02d}_{t}.mp3', TITLE=t, TRACKNUMBER=str(n), DISCNUMBER='1', **COMPLETE
		)
		for n, t in ((1, 'One'), (2, 'Two'))
	]


def test_a_complete_mp3_album_is_fixed(make_mp3: MakeMp3) -> None:
	folder = tagwright.ROOT / 'Test Artist-Test Album'
	mp3_album(make_mp3, folder)
	s = tagwright.summarize(folder)
	assert s['status'] == 'fixed' and [st['done'] for st in s['steps']] == [True] * 6
	assert s['tracks'] == 2 and s['files'][0]['channels'] == 1


def test_discogs_tags_are_written_to_mp3_files_and_a_second_run_changes_nothing(
	make_mp3: MakeMp3, tmp_path: Path
) -> None:
	folder = tmp_path / 'a'
	files = [
		make_mp3(
			folder / f'{i:02d}.mp3',
			DISCOGS_RELEASE_ID='123',
			ALBUM_DR='7',
			TITLE='t',
			CATALOGNUMBER='CAT-1',
			ALBUM_FORMAT='CD',
		)
		for i in (1, 2)
	]
	cfg = Config(data_dir=tmp_path / 'data')
	result = fixtags.fix_album(folder, cfg, get=FakeGet(ANSWERS))
	assert result.changed == 2 and result.version == '2020 DR07 CD (CAT-1)'
	for f in files:
		t = {k.upper(): list(v) for k, v in (audio.open_audio(f).tags or {}).items()}
		assert t['ALBUM'] == ['Master Title'] and t['DATE'] == ['2020']
		assert t['ORIGINALDATE'] == ['2001'] and t['ORIGINAL YEAR'] == ['2001']  # a TDOR and a TXXX
		assert t['ALBUM_COMPANY_PRESSED_BY'] == ['MPO'] and t['VERSION'] == ['2020 DR07 CD (CAT-1)']
	assert fixtags.fix_album(folder, cfg, get=FakeGet(ANSWERS)).changed == 0


def test_files_keep_their_own_extension_when_renamed(
	make_flac: MakeFlac, make_mp3: MakeMp3, tmp_path: Path
) -> None:
	folder = tmp_path / 'mixed'
	make_flac(folder / 'x.flac', TITLE='One', TRACKNUMBER='1', DISCNUMBER='1')
	make_mp3(folder / 'y.mp3', TITLE='Two', TRACKNUMBER='2', DISCNUMBER='1')
	make_mp3(folder / 'Z.MP3', TITLE='Three', TRACKNUMBER='3', DISCNUMBER='1')
	rename_files(folder)
	assert sorted(p.name for p in folder.iterdir()) == [
		'01_01_One.flac',
		'01_02_Two.mp3',
		'01_03_Three.mp3',
	]
	assert tagwright.file_name(
		{'TITLE': ['One'], 'TRACKNUMBER': ['1'], 'DISCNUMBER': ['1']}, '.mp3'
	) == ('01_01_One.mp3')


def test_the_planner_gives_each_file_its_own_extension() -> None:
	tags = {'ALBUMARTIST': 'A', 'ALBUM': 'B', 'TITLE': 'T', 'TRACKNUMBER': '1', 'DISCNUMBER': '1'}
	items = [
		planner.Item(PurePosixPath('x/one.flac'), tags),
		planner.Item(PurePosixPath('x/two.mp3'), {**tags, 'TITLE': 'U', 'TRACKNUMBER': '2'}),
	]
	moves = planner.plan(items, default()).moves
	assert sorted(PurePosixPath(m.dst).name for m in moves) == ['01_01_T.flac', '01_02_U.mp3']


@pytest.mark.usefixtures('sandbox')
def test_the_tag_editor_and_the_player_work_on_mp3(client: TestClient, make_mp3: MakeMp3) -> None:
	folder = tagwright.ROOT / 'Test Artist-Test Album'
	mp3_album(make_mp3, folder)
	r = client.get('/api/tags', params={'path': str(folder)}).json()
	assert r['fields']['ALBUM_FORMAT'] == 'CD' and r['tracks'][0]['title'] == 'One'
	assert 'REPLAYGAIN_ALBUM_GAIN' in {o['key'] for o in r['other']}
	r = client.post(
		'/api/tags',
		json={
			'path': str(folder),
			'fields': {},
			'tracks': [
				{'file': '01_01_One.mp3', 'title': 'Uno', 'disc': '1', 'track': '1', 'artist': 'X'}
			],
		},
	)
	assert r.status_code == 200, r.text
	assert (folder / '01_01_Uno.mp3').exists()  # renamed to the new title, still an mp3
	played = client.get('/api/audio', params={'path': str(folder), 'file': '01_02_Two.mp3'})
	assert played.status_code == 200 and played.headers['content-type'] == 'audio/mpeg'


def test_a_cover_is_embedded_and_measured_in_mp3_files(make_mp3: MakeMp3) -> None:
	import io

	from PIL import Image

	folder = tagwright.ROOT / 'Test Artist-Test Album'
	mp3_album(make_mp3, folder)
	buf = io.BytesIO()
	Image.new('RGB', (64, 48), 'blue').save(buf, 'PNG')
	tagwright.embed_cover(folder, tagwright.make_picture(buf.getvalue()))
	cover = tagwright.summarize(folder)['cover']
	assert cover and (cover['w'], cover['h'], cover['embedded']) == (64, 48, True)
	assert all(len(audio.open_audio(f).pictures) == 1 for f in sorted(folder.glob('*.mp3')))
