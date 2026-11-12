"""Running the pipeline through the API with fake steps: queue, 409 rules, rename, stop, move (ADR 0008, 0011, 0036)."""

import logging
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright
from pipeline import run
from pipeline.tools import Context, StepError

from .conftest import COMPLETE, MakeFlac

# What the real steps leave behind: every tag the six steps look at.
DONE_TAGS = {
	'DYNAMIC_RANGE': '10',
	'REPLAYGAIN_ALBUM_GAIN': '-6.00 dB',
	'ACOUSTID_FINGERPRINT': 'AQAA',
	'VERSION': '2020 DR10 CD (TST-001)',
}


def write_tags(album: Path, ctx: Context) -> None:
	"""A pipeline step that tags every file like the real ones do."""
	for f in sorted(album.rglob('*.flac')):
		a = FLAC(f)
		for k, v in DONE_TAGS.items():
			a[k] = [v]
		a.save()
	logging.getLogger('pipeline.test').info('tags written')


def use_steps(monkeypatch: pytest.MonkeyPatch, *steps: tuple[str, run.StepFn]) -> None:
	monkeypatch.setattr(run, 'STEPS', list(steps))


def wait_for_end(client: TestClient, timeout: float = 20) -> dict:
	deadline = time.time() + timeout
	while time.time() < deadline:
		j = client.get('/api/job').json()
		if j['state'] != 'running':
			return j
		time.sleep(0.05)
	raise AssertionError('job did not finish')


def open_album(make_flac: MakeFlac, name: str = 'Open Album') -> Path:
	"""An album that still needs the pipeline: Discogs ID and required tags, but no DR, gain, fingerprint, version."""
	folder = tagwright.ROOT / name
	base = {
		k: v
		for k, v in COMPLETE.items()
		if k
		not in (
			'DYNAMIC_RANGE',
			'ALBUM_DR',
			'VERSION',
			'REPLAYGAIN_ALBUM_GAIN',
			'ACOUSTID_FINGERPRINT',
		)
	}
	for number, title in ((1, 'One'), (2, 'Two')):
		make_flac(
			folder / f'track{number}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**base,
		)
	return folder


def blocking_step(started: threading.Event) -> run.StepFn:
	def block(album: Path, ctx: Context) -> None:
		started.set()
		ctx.stop.wait(30)
		ctx.check()

	return block


def test_run_fixes_the_album_and_renames_files(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)
	use_steps(monkeypatch, ('fake pipeline', write_tags))
	assert tagwright.fresh_summary(folder)['status'] == 'ready'

	assert client.post('/api/run', json={'path': str(folder)}).json() == {'ok': True, 'count': 1}
	job = wait_for_end(client)

	assert (job['state'], job['rc']) == ('done', 0)
	assert job['lines'][:2] == [
		'=== Open Album ===',
		'-- fake pipeline',
	]  # what the pipeline logs reaches the job log
	assert 'tags written' in job['lines']
	assert '-- rename files' in job['lines']
	assert sorted(f.name for f in tagwright.flacs(folder)) == ['01_01_One.flac', '01_02_Two.flac']
	s = tagwright.fresh_summary(folder)
	assert (s['status'], s['steps_done']) == ('fixed', 6)


def test_a_failing_step_is_logged_the_job_fails_but_the_rest_and_the_rename_still_run(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)

	def boom(album: Path, ctx: Context) -> None:
		raise StepError('drcalc exited with code 1')

	use_steps(monkeypatch, ('Dynamic range', boom), ('rest', write_tags))
	client.post('/api/run', json={'path': str(folder)})
	job = wait_for_end(client)
	assert (job['state'], job['rc']) == ('failed', 1)
	assert 'Dynamic range failed: drcalc exited with code 1' in job['lines']
	assert 'tags written' in job['lines']  # the next step still ran
	assert '-- rename files' in job['lines']


def test_the_pipeline_log_handler_is_removed_after_the_job(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)
	use_steps(monkeypatch, ('fake', write_tags))
	client.post('/api/run', json={'path': str(folder)})
	wait_for_end(client)
	assert not [
		h for h in logging.getLogger('pipeline').handlers if isinstance(h, tagwright.JobLog)
	]


def test_queue_runs_albums_one_after_another_and_continues_after_a_failure(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	first = open_album(make_flac)
	second = open_album(make_flac, 'Second')

	def step(album: Path, ctx: Context) -> None:
		if album.name == 'Open Album':
			raise StepError('first album fails')
		write_tags(album, ctx)

	use_steps(monkeypatch, ('step', step))
	assert client.post('/api/run', json={'paths': [str(first), str(second)]}).json()['count'] == 2
	job = wait_for_end(client)
	assert job['state'] == 'failed'  # the first failed ...
	assert job['queue'] == []
	assert '=== Second ===' in job['lines']  # ... and the second still ran
	assert tagwright.fresh_summary(second)['status'] == 'fixed'


def test_album_that_needs_input_is_refused(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = tagwright.ROOT / 'NoDiscogs'
	make_flac(folder / 'a.flac', TITLE='x')
	use_steps(monkeypatch, ('fake', write_tags))
	assert client.post('/api/run', json={'path': str(folder)}).status_code == 409
	assert tagwright.job['state'] == 'idle'


def test_run_outside_root_is_refused(client: TestClient, tmp_path: Path) -> None:
	assert client.post('/api/run', json={'path': str(tmp_path)}).status_code == 400
	assert client.get('/api/album', params={'path': '/etc'}).status_code == 400


def test_second_run_and_writes_are_refused_while_a_job_runs(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch, album: Path
) -> None:
	folder = open_album(make_flac)
	started = threading.Event()
	use_steps(monkeypatch, ('block', blocking_step(started)))
	assert client.post('/api/run', json={'path': str(folder)}).status_code == 200
	try:
		assert started.wait(10)
		assert client.post('/api/run', json={'path': str(folder)}).status_code == 409
		assert client.post('/api/move', json={'path': str(album)}).status_code == 409
		assert (
			client.post('/api/overrides', json={'path': str(album), 'artist': 'x'}).status_code
			== 409
		)
		assert client.get('/api/job').json()['state'] == 'running'
	finally:
		client.post('/api/stop')
		wait_for_end(client)


def test_stop_ends_the_step_and_skips_the_rename(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)
	started = threading.Event()
	use_steps(monkeypatch, ('block', blocking_step(started)), ('after', write_tags))
	client.post('/api/run', json={'path': str(folder)})
	assert started.wait(10)
	assert client.post('/api/stop').json() == {'ok': True}
	job = wait_for_end(client)
	assert job['state'] == 'stopped'
	assert '-- stopped by user' in job['lines']
	assert '-- rename files' not in job['lines']
	assert 'tags written' not in job['lines']  # the remaining steps did not run
	assert (folder / 'track1.flac').is_file()


def test_stop_clears_the_queue(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	first, second = open_album(make_flac), open_album(make_flac, 'Second')
	started = threading.Event()
	use_steps(monkeypatch, ('block', blocking_step(started)))
	client.post('/api/run', json={'paths': [str(first), str(second)]})
	assert started.wait(10)
	assert client.get('/api/job').json()['queue'] == [str(second)]
	client.post('/api/stop')
	job = wait_for_end(client)
	assert job['queue'] == []
	assert '=== Second ===' not in job['lines']


def test_the_job_names_the_step_that_is_running(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)
	seen: list[str] = []
	started = threading.Event()
	release = threading.Event()

	def watch(name: str) -> run.StepFn:
		def step(album: Path, ctx: Context) -> None:
			seen.append(client.get('/api/job').json()['step'])
			if name == 'Lyrics':
				started.set()
				release.wait(10)

		return step

	use_steps(
		monkeypatch,
		*((n, watch(n)) for n in ('dot_clean', 'Dynamic range', 'Discogs tags', 'Lyrics')),
	)
	client.post('/api/run', json={'path': str(folder)})
	assert started.wait(10)
	assert seen == [
		'',
		'Dynamic range',
		'Tags and cover',
		'Lyrics',
	]  # the names of the UI's pipeline row; dot_clean has none
	release.set()
	job = wait_for_end(client)
	assert job['step'] == ''  # nothing is running any more


def test_the_rename_is_the_filenames_step(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	folder = open_album(make_flac)
	steps: list[str] = []
	monkeypatch.setattr(
		tagwright,
		'rename_files',
		lambda album, name_of=None: steps.append(tagwright.job['step']) or ['ok'],
	)
	use_steps(monkeypatch, ('fake', write_tags))
	client.post('/api/run', json={'path': str(folder)})
	wait_for_end(client)
	assert steps == ['Filenames']


def test_stop_without_a_job_is_409(client: TestClient) -> None:
	assert client.post('/api/stop').status_code == 409


def test_move_places_a_fixed_album_in_the_library_layout_and_never_overwrites(
	client: TestClient, album: Path, make_flac: MakeFlac
) -> None:
	where = tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001'
	r = client.post('/api/move', json={'path': str(album)})
	assert r.json() == {'moved_to': str(where)}
	assert sorted(f.name for f in where.glob('*.flac')) == ['01_01_One.flac', '01_02_Two.flac']
	assert not tagwright.flacs(album)

	again = tagwright.ROOT / album.name  # the same album again: the target names exist
	for number, title in ((1, 'One'), (2, 'Two')):
		make_flac(
			again / f'01_{number:02d}_{title}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**COMPLETE,
		)
	r = client.post('/api/move', json={'path': str(again)})
	assert r.status_code == 409
	assert 'already exists' in r.json()['detail']
	assert len(tagwright.flacs(again)) == 2  # nothing was merged or removed


def test_move_makes_disc_folders_for_a_multi_disc_album(
	client: TestClient, make_flac: MakeFlac
) -> None:
	folder = tagwright.ROOT / 'Box'
	for disc in (1, 2):
		make_flac(
			folder / f'0{disc}_01_x.flac',
			TITLE='x',
			TRACKNUMBER='1',
			DISCNUMBER=str(disc),
			**COMPLETE,
		)
	r = client.post('/api/move', json={'path': str(folder)})
	assert r.status_code == 200
	where = tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001'
	assert sorted(p.relative_to(where).as_posix() for p in where.rglob('*.flac')) == [
		'Disc 1/01_01_x.flac',
		'Disc 2/02_01_x.flac',
	]


def test_a_single_disc_album_joins_an_existing_multi_disc_one(
	client: TestClient, album: Path
) -> None:
	(tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001' / 'Disc 2').mkdir(
		parents=True
	)
	client.post('/api/move', json={'path': str(album)})
	assert (
		tagwright.INGEST
		/ 'Test_Artist'
		/ 'Test_Album_2020_DR10_CD_TST_001'
		/ 'Disc 1'
		/ '01_01_One.flac'
	).is_file()


def test_move_refuses_files_the_layout_cannot_place(client: TestClient, album: Path) -> None:
	f = FLAC(tagwright.flacs(album)[0])
	f['TITLE'] = ['']
	f.save()  # a title that is empty: the album is no longer fixed, so it is refused earlier
	assert client.post('/api/move', json={'path': str(album)}).status_code == 409
	assert not (tagwright.INGEST / 'Test_Artist').exists()


def test_move_uses_the_configured_template(
	client: TestClient, album: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	template = {
		'folders': [[{'tag': 'ALBUM', 'fmt': 'text'}]],
		'filename': [
			{'tag': 'TRACKNUMBER', 'fmt': 'num', 'pad': 2},
			{'text': ' '},
			{'tag': 'TITLE', 'fmt': 'text'},
		],
		'disc_folder': None,
	}
	monkeypatch.setattr(tagwright, 'settings', {'library': {'template': template}})
	assert (
		tagwright.fresh_summary(album)['status'] == 'ready'
	)  # the files still carry the bliss names
	tagwright.rename_files(album, tagwright.file_name)  # what a run does after the steps
	assert client.post('/api/move', json={'path': str(album)}).status_code == 200
	assert (tagwright.INGEST / 'Test_Album' / '01 One.flac').is_file()


def test_move_refuses_an_album_that_is_not_fixed(client: TestClient, make_flac: MakeFlac) -> None:
	folder = open_album(make_flac)
	assert client.post('/api/move', json={'path': str(folder)}).status_code == 409
	assert not (tagwright.INGEST / folder.name).exists()


def test_move_refuses_a_small_cover(
	client: TestClient, album: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(tagwright, 'MIN_COVER', 1400)
	assert client.post('/api/move', json={'path': str(album)}).status_code == 409


def test_move_preview_says_what_would_happen_without_doing_it(
	client: TestClient, album: Path
) -> None:
	p = client.get('/api/move/preview', params={'path': str(album)}).json()
	assert p['library'] == str(tagwright.INGEST)
	assert p['album_dir'] == 'Test_Artist/Test_Album_2020_DR10_CD_TST_001'
	assert [f['name'] for f in p['files']] == ['01_01_One.flac', '01_02_Two.flac']
	assert (p['can_move'], p['problems']) == (True, [])
	assert 'Only the FLAC files move' in p['stays']
	assert len(tagwright.flacs(album)) == 2  # nothing moved
	assert not (tagwright.INGEST / 'Test_Artist').exists()


def test_move_preview_lists_every_reason_the_move_is_refused(
	client: TestClient, album: Path
) -> None:
	where = tagwright.INGEST / 'Test_Artist' / 'Test_Album_2020_DR10_CD_TST_001'
	where.mkdir(parents=True)
	(where / '01_01_One.flac').write_bytes(b'x')
	p = client.get('/api/move/preview', params={'path': str(album)}).json()
	assert p['can_move'] is False
	assert any('already exists' in x for x in p['problems'])
	assert [f['exists'] for f in p['files']] == [True, False]
	assert client.post('/api/move', json={'path': str(album)}).status_code == 409


def test_move_preview_for_an_album_that_is_not_fixed(
	client: TestClient, make_flac: MakeFlac
) -> None:
	p = client.get('/api/move/preview', params={'path': str(open_album(make_flac))}).json()
	assert (p['can_move'], 'not fully fixed' in ' '.join(p['problems'])) == (False, True)


def test_move_preview_outside_the_root_is_refused(client: TestClient, tmp_path: Path) -> None:
	assert client.get('/api/move/preview', params={'path': str(tmp_path)}).status_code == 400


def test_a_single_step_runs_alone_and_the_others_do_not(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""ADR 0051: {step} runs only that step; Dynamic range alone does not rename the files."""
	ran: list[str] = []
	use_steps(
		monkeypatch,
		('Dynamic range', lambda a, c: ran.append('dr')),
		('ReplayGain', lambda a, c: ran.append('rg')),
		('Lyrics', lambda a, c: ran.append('lyrics')),
	)
	album = open_album(make_flac)
	r = client.post('/api/run', json={'path': str(album), 'step': 'ReplayGain'})
	assert r.status_code == 200
	wait_for_end(client)
	assert ran == ['rg']
	assert sorted(f.name for f in album.glob('*.flac')) == [
		'track1.flac',
		'track2.flac',
	]  # no rename
	assert client.post('/api/run', json={'path': str(album), 'step': 'Nope'}).status_code == 400
	r = client.post('/api/run', json={'path': str(album), 'step': 'Filenames'})
	wait_for_end(client)
	assert ran == ['rg']  # no pipeline step
	assert sorted(f.name for f in album.glob('*.flac')) != ['track1.flac', 'track2.flac']  # renamed


def test_audio_steps_run_on_an_album_that_needs_input_the_others_do_not(
	client: TestClient, make_flac: MakeFlac, monkeypatch: pytest.MonkeyPatch
) -> None:
	ran: list[str] = []
	use_steps(
		monkeypatch,
		('Dynamic range', lambda a, c: ran.append('dr')),
		('Lyrics', lambda a, c: ran.append('lyrics')),
	)
	album = open_album(make_flac, 'No Discogs')
	for f in album.glob('*.flac'):
		a = FLAC(f)
		del a['DISCOGS_RELEASE_ID']
		a.save()
	assert tagwright.summarize(album)['status'] == 'needs'
	assert (
		client.post('/api/run', json={'path': str(album), 'step': 'Dynamic range'}).status_code
		== 200
	)
	wait_for_end(client)
	assert ran == ['dr']
	assert client.post('/api/run', json={'path': str(album), 'step': 'Lyrics'}).status_code == 409
	assert client.post('/api/run', json={'path': str(album)}).status_code == 409
