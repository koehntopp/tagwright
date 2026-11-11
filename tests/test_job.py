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


def test_stop_without_a_job_is_409(client: TestClient) -> None:
	assert client.post('/api/stop').status_code == 409


def test_move_takes_only_fixed_albums_and_never_overwrites(
	client: TestClient, album: Path, make_flac: MakeFlac
) -> None:
	dest = tagwright.INGEST / album.name
	r = client.post('/api/move', json={'path': str(album)})
	assert r.json() == {'moved_to': str(dest)}
	assert sorted(f.name for f in dest.glob('*.flac')) == ['01_01_One.flac', '01_02_Two.flac']
	assert not album.exists() or not tagwright.flacs(album)

	again = tagwright.ROOT / album.name  # same folder name again: destination exists
	for number, title in ((1, 'One'), (2, 'Two')):
		make_flac(
			again / f'01_{number:02d}_{title}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**COMPLETE,
		)
	assert client.post('/api/move', json={'path': str(again)}).status_code == 409
	assert len(tagwright.flacs(again)) == 2  # nothing was merged or removed


def test_move_refuses_an_album_that_is_not_fixed(client: TestClient, make_flac: MakeFlac) -> None:
	folder = open_album(make_flac)
	assert client.post('/api/move', json={'path': str(folder)}).status_code == 409
	assert not (tagwright.INGEST / folder.name).exists()


def test_move_refuses_a_small_cover(
	client: TestClient, album: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(tagwright, 'MIN_COVER', 1400)
	assert client.post('/api/move', json={'path': str(album)}).status_code == 409
