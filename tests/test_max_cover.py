"""The maximum cover size is a setting (default 1500): it reaches uploads, fetched covers and the pipeline (ADR 0074)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as tagwright


def png(width: int, height: int) -> bytes:
	buf = io.BytesIO()
	Image.new('RGB', (width, height), 'red').save(buf, 'PNG')
	return buf.getvalue()


def body(**extra: object) -> dict:
	return {'input': str(tagwright.ROOT), 'output': str(tagwright.INGEST), **extra}


def test_the_default_is_1500_and_the_setting_is_saved(client: TestClient) -> None:
	assert tagwright.MAX_COVER == 1500 and client.get('/api/settings').json()['max_cover'] == 1500
	r = client.post('/api/settings', json=body(max_cover='900'))
	assert r.status_code == 200 and r.json()['max_cover'] == 900
	assert tagwright.MAX_COVER == 900 and tagwright.settings['max_cover'] == 900
	assert client.post('/api/settings', json=body()).json()['max_cover'] == 900  # absent: unchanged


@pytest.mark.parametrize(
	('extra', 'message'),
	[
		({'max_cover': 'big'}, 'whole number'),
		({'max_cover': 50}, 'between 100 and 20000'),
		({'max_cover': 30000}, 'between 100 and 20000'),
		({'min_cover': 1400, 'max_cover': 1000}, 'must not be below the minimum'),
	],
)
def test_a_bad_maximum_is_refused_and_changes_nothing(
	client: TestClient, extra: dict, message: str
) -> None:
	r = client.post('/api/settings', json=body(**extra))
	assert r.status_code == 400 and message in r.json()['detail']
	assert tagwright.MAX_COVER == 1500


def test_an_uploaded_cover_is_scaled_to_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(tagwright, 'MAX_COVER', 600)
	pic = tagwright.make_picture(png(1000, 800))
	assert (pic.width, pic.height) == (600, 480)
	monkeypatch.setattr(tagwright, 'MAX_COVER', 2000)
	assert (tagwright.make_picture(png(1000, 800)).width) == 1000  # smaller than the maximum: kept


def test_the_pipeline_gets_the_same_maximum(monkeypatch: pytest.MonkeyPatch) -> None:
	assert tagwright.app_config().cover_max_size == 1500
	monkeypatch.setattr(tagwright, 'MAX_COVER', 1200)
	assert tagwright.app_config().cover_max_size == 1200
