"""Running the pipeline through the API with a fake nzbfix: queue, 409 rules, rename, stop, move (ADR 0004, 0008, 0011)."""

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

import app as tagwright

from .conftest import COMPLETE, MakeFlac

FakeNzbfix = Callable[[str], Path]

# What the real nzbfix leaves behind: every tag the six steps look at.
WRITE_TAGS = """
from pathlib import Path
from mutagen.flac import FLAC
for f in sorted(Path(album).rglob('*.flac')):
	a = FLAC(f)
	a['DYNAMIC_RANGE'] = ['10']
	a['REPLAYGAIN_ALBUM_GAIN'] = ['-6.00 dB']
	a['ACOUSTID_FINGERPRINT'] = ['AQAA']
	a['VERSION'] = ['2020 DR10 CD (TST-001)']
	a.save()
print('nzbfix done')
"""


def wait_for_end(client: TestClient, timeout: float = 20) -> dict:
	deadline = time.time() + timeout
	while time.time() < deadline:
		j = client.get('/api/job').json()
		if j['state'] != 'running':
			return j
		time.sleep(0.05)
	raise AssertionError('job did not finish')


def open_album(make_flac: MakeFlac) -> Path:
	"""An album that still needs the pipeline: Discogs ID and required tags, but no DR, gain, fingerprint, version."""
	folder = tagwright.ROOT / 'Open Album'
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


def test_run_fixes_the_album_and_renames_files(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix
) -> None:
	folder = open_album(make_flac)
	fake_nzbfix(WRITE_TAGS)
	assert tagwright.fresh_summary(folder)['status'] == 'ready'

	assert client.post('/api/run', json={'path': str(folder)}).json() == {'ok': True, 'count': 1}
	job = wait_for_end(client)

	assert job['state'] == 'done'
	assert job['rc'] == 0
	assert 'nzbfix done' in job['lines']
	assert '-- rename files' in job['lines']
	assert sorted(f.name for f in tagwright.flacs(folder)) == ['01_01_One.flac', '01_02_Two.flac']
	s = tagwright.fresh_summary(folder)
	assert s['status'] == 'fixed'
	assert s['steps_done'] == 6


def test_failed_nzbfix_marks_the_job_failed_and_skips_the_rename(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix
) -> None:
	folder = open_album(make_flac)
	fake_nzbfix('print("boom")\nsys.exit(3)')
	client.post('/api/run', json={'path': str(folder)})
	job = wait_for_end(client)
	assert (job['state'], job['rc']) == ('failed', 1)
	assert '-- rename files' not in job['lines']
	assert (folder / 'track1.flac').is_file()


def test_queue_runs_albums_one_after_another_and_continues_after_a_failure(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix
) -> None:
	first = open_album(make_flac)
	second = tagwright.ROOT / 'Second'
	for f in tagwright.flacs(first):
		FLAC(f).save()  # untouched, only to keep the fixture simple
	for number, title in ((1, 'A'), (2, 'B')):
		make_flac(
			second / f't{number}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**{
				k: v
				for k, v in COMPLETE.items()
				if k
				in (
					'ARTIST',
					'ALBUMARTIST',
					'ALBUM',
					'DATE',
					'ALBUM_FORMAT',
					'CATALOGNUMBER',
					'DISCOGS_RELEASE_ID',
				)
			},
		)
	fake_nzbfix(f'if "Open Album" in album:\n\tsys.exit(1)\n{WRITE_TAGS}')
	r = client.post('/api/run', json={'paths': [str(first), str(second)]})
	assert r.json()['count'] == 2
	job = wait_for_end(client)
	assert job['state'] == 'failed'  # the first failed ...
	assert job['queue'] == []
	assert any('=== Second ===' in line for line in job['lines'])  # ... and the second still ran
	assert (second / '01_01_A.flac').is_file()


def test_album_that_needs_input_is_refused(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix
) -> None:
	folder = tagwright.ROOT / 'NoDiscogs'
	make_flac(folder / 'a.flac', TITLE='x')
	fake_nzbfix(WRITE_TAGS)
	r = client.post('/api/run', json={'path': str(folder)})
	assert r.status_code == 409
	assert tagwright.job['state'] == 'idle'


def test_run_outside_root_is_refused(client: TestClient, tmp_path: Path) -> None:
	assert client.post('/api/run', json={'path': str(tmp_path)}).status_code == 400
	assert client.get('/api/album', params={'path': '/etc'}).status_code == 400


def test_second_run_and_writes_are_refused_while_a_job_runs(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix, album: Path
) -> None:
	folder = open_album(make_flac)
	fake_nzbfix('import time\ntime.sleep(30)')
	assert client.post('/api/run', json={'path': str(folder)}).status_code == 200
	try:
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


def test_stop_ends_nzbfix_and_skips_the_rename(
	client: TestClient, make_flac: MakeFlac, fake_nzbfix: FakeNzbfix
) -> None:
	folder = open_album(make_flac)
	fake_nzbfix('import time\nprint("started", flush=True)\ntime.sleep(60)')
	client.post('/api/run', json={'path': str(folder)})
	deadline = time.time() + 10
	while 'started' not in client.get('/api/job').json()['lines'] and time.time() < deadline:
		time.sleep(0.05)
	assert client.post('/api/stop').json() == {'ok': True}
	job = wait_for_end(client)
	assert job['state'] == 'stopped'
	assert '-- stopped by user' in job['lines']
	assert '-- rename files' not in job['lines']


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
