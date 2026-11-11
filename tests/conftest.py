"""Fixtures for the Tagwright tests (ADR 0035).

Everything runs on synthetic FLAC files in pytest's tmp_path; ROOT, INGEST_DIR, DATA_DIR and DISCOGS_DIR
never point at a real library (ADR 0018). The environment is set before app.py is imported, because app.py
reads it at import time (and would otherwise read data/settings.json of the real instance).
"""

import os
import stat
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

_BOOT = Path(tempfile.mkdtemp(prefix='tagwright-test-'))
for _name in ('root', 'ingest', 'data', 'scripts'):
	(_BOOT / _name).mkdir()
os.environ.update(
	ROOT=str(_BOOT / 'root'),
	INGEST_DIR=str(_BOOT / 'ingest'),
	DATA_DIR=str(_BOOT / 'data'),
	DISCOGS_DIR=str(_BOOT / 'scripts'),
)

import numpy as np  # noqa: E402  # after the environment is set, see the module docstring
import pytest  # noqa: E402
import soundfile as sf  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from mutagen.flac import FLAC  # noqa: E402

import app as tagwright  # noqa: E402

MakeFlac = Callable[..., Path]

# A complete, consistent tag set: every pipeline step done, nothing missing.
COMPLETE: dict[str, str] = {
	'ARTIST': 'Test Artist',
	'ALBUMARTIST': 'Test Artist',
	'ALBUM': 'Test Album',
	'DATE': '2020',
	'ALBUM_FORMAT': 'CD',
	'CATALOGNUMBER': 'TST-001',
	'VERSION': '2020 DR10 CD (TST-001)',
	'DISCOGS_RELEASE_ID': '12345',
	'DYNAMIC_RANGE': '10',
	'ALBUM_DR': '10',
	'REPLAYGAIN_ALBUM_GAIN': '-6.00 dB',
	'ACOUSTID_FINGERPRINT': 'AQAA',
	'LYRICS': '[00:01.00]la la',
}


@pytest.fixture(autouse=True)
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
	"""Fresh ROOT, INGEST and SCRIPTS per test, empty job state, no cover minimum (the fixtures have no art)."""
	root, ingest, scripts = tmp_path / 'root', tmp_path / 'ingest', tmp_path / 'scripts'
	for d in (root, ingest, scripts):
		d.mkdir()
	monkeypatch.setattr(tagwright, 'ROOT', root)
	monkeypatch.setattr(tagwright, 'INGEST', ingest)
	monkeypatch.setattr(tagwright, 'SCRIPTS', scripts)
	monkeypatch.setattr(tagwright, 'MIN_COVER', 0)
	monkeypatch.setattr(tagwright, 'settings', {})
	tagwright.cache.clear()
	tagwright.job.update(
		path=None, state='idle', lines=[], rc=None, queue=[], stop=False, proc=None
	)
	assert root.is_relative_to(tmp_path)  # ADR 0018: never a real library
	yield
	proc = tagwright.job.get('proc')
	if proc is not None and proc.poll() is None:  # a test left nzbfix running
		proc.kill()


@pytest.fixture
def client() -> TestClient:
	return TestClient(tagwright.app)


@pytest.fixture
def make_flac() -> MakeFlac:
	"""make_flac(path, rate=44100, **tags) writes a 0.2 s silent FLAC with the given tags and returns the path."""

	def make(path: Path, rate: int = 44100, **tags: str) -> Path:
		path.parent.mkdir(parents=True, exist_ok=True)
		sf.write(path, np.zeros(rate // 5, dtype='int16'), rate, format='FLAC')
		audio = FLAC(path)
		if audio.tags is None:  # soundfile may already write an empty Vorbis comment
			audio.add_tags()
		for key, value in tags.items():
			audio[key] = [value]
		audio.save()
		return path

	return make


@pytest.fixture
def album(make_flac: MakeFlac) -> Path:
	"""A complete two-track album under ROOT, named as the bliss pattern wants."""
	folder = tagwright.ROOT / 'Test Artist-Test Album'
	for number, title in ((1, 'One'), (2, 'Two')):
		make_flac(
			folder / f'01_{number:02d}_{title}.flac',
			TITLE=title,
			TRACKNUMBER=str(number),
			DISCNUMBER='1',
			**COMPLETE,
		)
	return folder


@pytest.fixture
def fake_nzbfix() -> Callable[[str], Path]:
	"""fake_nzbfix(body) installs an executable nzbfix.py (Python) in SCRIPTS; body runs with argv[1] = album."""

	def install(body: str) -> Path:
		script = tagwright.SCRIPTS / 'nzbfix.py'
		script.write_text(f'#!{sys.executable}\nimport sys\nalbum = sys.argv[1]\n{body}\n')
		script.chmod(script.stat().st_mode | stat.S_IXUSR)
		return script

	return install
