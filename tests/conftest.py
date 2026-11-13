"""Fixtures for the Tagwright tests (ADR 0035).

Everything runs on synthetic FLAC files in pytest's tmp_path; STAGING_FOLDER, LIBRARY_FOLDER and DATA_DIR
never point at a real library (ADR 0018). The environment is set before app.py is imported, because app.py
reads it at import time (and would otherwise read data/settings.json of the real instance).
"""

import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

_BOOT = Path(tempfile.mkdtemp(prefix='tagwright-test-'))
for _name in ('root', 'ingest', 'data'):
	(_BOOT / _name).mkdir()
os.environ.update(
	STAGING_FOLDER=str(_BOOT / 'root'),
	LIBRARY_FOLDER=str(_BOOT / 'ingest'),
	DATA_DIR=str(_BOOT / 'data'),
)

import numpy as np  # noqa: E402  # after the environment is set, see the module docstring
import pytest  # noqa: E402  # same reason
import soundfile as sf  # noqa: E402  # same reason
from fastapi.testclient import TestClient  # noqa: E402  # same reason
from mutagen.flac import FLAC  # noqa: E402  # same reason

import app as tagwright  # noqa: E402  # same reason
from pipeline import layout  # noqa: E402  # same reason

MakeFlac = Callable[..., Path]
MakeMp3 = Callable[..., Path]

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
	"""Fresh ROOT and INGEST per test, empty job state, no cover minimum (the fixtures have no art)."""
	root, ingest = tmp_path / 'root', tmp_path / 'ingest'
	for d in (root, ingest):
		d.mkdir()
	monkeypatch.setattr(tagwright, 'ROOT', root)
	monkeypatch.setattr(layout, 'STAGING', root)
	monkeypatch.setattr(tagwright, 'INGEST', ingest)
	monkeypatch.setattr(tagwright, 'MIN_COVER', 0)
	monkeypatch.setattr(tagwright, 'MAX_COVER', 1500)
	monkeypatch.setattr(tagwright, 'settings', {})
	tagwright.cache.clear()
	tagwright.job.update(
		path=None, state='idle', lines=[], rc=None, queue=[], stop=False, ctx=None, step=''
	)
	assert root.is_relative_to(tmp_path)  # ADR 0018: never a real library
	yield
	ctx = tagwright.job.get('ctx')
	if ctx is not None:  # a test left a job running
		ctx.kill()


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
def make_mp3() -> MakeMp3:
	"""make_mp3(path, **tags) writes a one-second silent MP3 with the given tags (ID3v2.4 through the adapter)."""
	from pipeline.audio import (
		open_audio,  # after the environment is set, like the other app imports
	)

	def make(path: Path, rate: int = 44100, **tags: str) -> Path:
		path.parent.mkdir(parents=True, exist_ok=True)
		sf.write(path, np.zeros(rate, dtype='int16'), rate, format='MP3')
		audio = open_audio(path)
		audio.add_tags()
		for key, value in tags.items():
			audio[key] = [value]
		audio.save()
		return path

	return make
