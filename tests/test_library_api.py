"""The library endpoints and settings (ADR 0037, 0009)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as tagwright
from library.template import default

from .conftest import MakeFlac


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Settings are written to the temp data directory, and the real watcher is not started."""
	monkeypatch.setattr(tagwright, 'DATA', tmp_path / 'data')
	monkeypatch.setattr(tagwright, 'SETTINGS_FILE', tmp_path / 'data' / 'settings.json')
	calls: list[str] = []
	monkeypatch.setattr(tagwright.library, 'rescan', lambda: calls.append('rescan'))
	monkeypatch.setattr(tagwright.library, 'poke', lambda: calls.append('poke'))
	monkeypatch.setattr(tagwright, 'LIBRARY_CALLS', calls, raising=False)


def post(client: TestClient, library: dict | None = None, **extra: object) -> object:
	body = {'input': str(tagwright.ROOT), 'output': str(tagwright.INGEST), **extra}
	if library is not None:
		body['library'] = library
	return client.post('/api/settings', json=body)


def test_settings_carry_the_library_defaults_the_palette_and_the_bliss_template(
	client: TestClient,
) -> None:
	lib = client.get('/api/settings').json()['library']
	assert (lib['apply'], lib['cooldown'], lib['interval'], lib['sweep_hours']) == (
		True,
		60,
		120,
		24,
	)
	assert lib['template'] == lib['default_template'] == default().to_dict()
	assert {'key': 'ALBUMARTIST', 'label': 'Album artist'} in lib['palette']


def test_library_settings_are_saved_and_a_new_template_triggers_a_full_pass(
	client: TestClient,
) -> None:
	template = {
		'folders': [
			[{'tag': 'ALBUMARTIST'}],
			[{'tag': 'DATE', 'fmt': 'year'}, {'text': ' - '}, {'tag': 'ALBUM'}],
		],
		'filename': [
			{'tag': 'TRACKNUMBER', 'fmt': 'num', 'pad': 2},
			{'text': ' '},
			{'tag': 'TITLE'},
		],
		'disc_folder': None,
	}
	r = post(client, {'apply': False, 'cooldown': 5, 'interval': 30, 'template': template})
	assert r.status_code == 200
	lib = r.json()['library']
	assert (lib['apply'], lib['cooldown'], lib['interval']) == (False, 5, 30)
	assert lib['template']['folders'][1][1] == {'text': ' - '}
	assert json.loads(tagwright.SETTINGS_FILE.read_text())['library']['apply'] is False
	assert tagwright.LIBRARY_CALLS == ['rescan']


def test_other_settings_changes_only_poke_the_watcher(client: TestClient) -> None:
	post(client, {'cooldown': 10})
	assert tagwright.LIBRARY_CALLS == ['poke']


@pytest.mark.parametrize(
	('library', 'message'),
	[
		({'cooldown': -1}, 'cooldown'),
		({'cooldown': 'soon'}, 'cooldown'),
		({'interval': 1}, 'interval'),
		({'sweep_hours': 0}, 'sweep_hours'),
		({'template': {'folders': [], 'filename': [{'tag': 'TITLE'}]}}, 'Template'),
		(
			{'template': {'folders': [[{'tag': 'NOPE'}]], 'filename': [{'tag': 'TITLE'}]}},
			'unknown tag',
		),
		({'template': 'x'}, 'malformed'),
	],
)
def test_bad_library_settings_are_refused_and_nothing_is_saved(
	client: TestClient, library: dict, message: str
) -> None:
	r = post(client, library)
	assert r.status_code == 400
	assert message in r.json()['detail']
	assert not tagwright.SETTINGS_FILE.exists()


def test_the_keys_stay_when_library_settings_change(client: TestClient) -> None:
	post(client, None, discogs_api_key='SECRET1234')
	post(client, {'cooldown': 7})
	assert tagwright.settings['discogs_api_key'] == 'SECRET1234'
	assert tagwright.settings['library']['cooldown'] == 7


def test_a_stored_template_that_is_invalid_falls_back_to_the_default(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr(
		tagwright,
		'settings',
		{'library': {'template': {'folders': [], 'filename': []}, 'cooldown': 'x'}},
	)
	cfg = tagwright.library_settings()
	assert cfg.template == default()
	assert cfg.cooldown == 60.0


def test_status_rescan_and_preview(client: TestClient, make_flac: MakeFlac) -> None:
	s = client.get('/api/library').json()
	assert s['apply'] is True
	assert 'phase' in s
	assert client.post('/api/library/rescan').json() == {'ok': True}
	assert tagwright.LIBRARY_CALLS == ['rescan']
	bad = client.post(
		'/api/library/preview', json={'template': {'folders': [], 'filename': []}}
	).json()
	assert bad['errors']
	assert client.post('/api/library/preview', json={'template': 'x'}).status_code == 400


def test_the_server_starts_and_stops_the_watcher_with_its_lifespan(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	events: list[str] = []
	monkeypatch.setattr(tagwright.library, 'start', lambda: events.append('start'))
	monkeypatch.setattr(tagwright.library, 'stop', lambda: events.append('stop'))
	with TestClient(tagwright.app):
		assert events == ['start']
	assert events == ['start', 'stop']
