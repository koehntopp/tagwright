"""The shared rate-limited API client: pacing, retries and error mapping (ADR 0013, 0023, 0036)."""

import io
import json
import urllib.error
from email.message import Message
from typing import Any

import pytest

from pipeline import discogs
from pipeline.http import ApiError, RateLimitedApi


class Response:
	def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
		self.body = io.BytesIO(body)
		self.headers = headers or {}

	def read(self, n: int = -1) -> bytes:
		return self.body.read(n)

	def __enter__(self) -> Response:
		return self

	def __exit__(self, *exc: object) -> None:
		return None


def http_error(code: int, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
	msg = Message()
	for key, value in (headers or {}).items():
		msg[key] = value
	return urllib.error.HTTPError('http://x', code, 'err', msg, io.BytesIO(b''))


class Fake:
	"""An opener that plays back answers (a Response or an exception) and a clock that sleep() advances."""

	def __init__(self, *answers: Response | BaseException) -> None:
		self.answers = list(answers)
		self.requests: list[Any] = []
		self.sleeps: list[float] = []
		self.now = 1000.0

	def opener(self, req: Any, timeout: float) -> Response:
		self.requests.append(req)
		answer = self.answers.pop(0)
		if isinstance(answer, BaseException):
			raise answer
		return answer

	def sleep(self, seconds: float) -> None:
		self.sleeps.append(seconds)
		self.now += seconds

	def clock(self) -> float:
		return self.now


def make(fake: Fake, **kw: Any) -> RateLimitedApi:
	return RateLimitedApi(
		name='Test',
		base='https://example.test',
		headers=lambda: {'User-Agent': 'tests'},
		interval=kw.pop('interval', 1.0),
		opener=fake.opener,
		sleep=fake.sleep,
		clock=fake.clock,
		**kw,
	)


def ok(data: object, headers: dict[str, str] | None = None) -> Response:
	return Response(json.dumps(data).encode(), headers)


def test_get_returns_json_and_builds_the_url() -> None:
	fake = Fake(ok({'a': 1}))
	api = make(fake)
	assert api.get('/x', q='a b', n=2) == {'a': 1}
	assert fake.requests[0].full_url == 'https://example.test/x?q=a+b&n=2'
	assert fake.requests[0].get_header('User-agent') == 'tests'


def test_requests_are_spaced_by_the_interval() -> None:
	fake = Fake(ok({}), ok({}))
	api = make(fake, interval=1.1)
	api.get('/a')
	fake.sleeps.clear()
	api.get('/b')
	assert fake.sleeps == [pytest.approx(1.1)]  # no time passed between the calls


def test_low_remaining_budget_pauses() -> None:
	fake = Fake(ok({}, {'X-Remaining': '2'}), ok({}, {'X-Remaining': '30'}))
	api = make(fake, low_header='X-Remaining', low_pause=5.0)
	api.get('/a')
	assert 5.0 in fake.sleeps
	fake.sleeps.clear()
	api.get('/b')
	assert 5.0 not in fake.sleeps


def test_404_is_not_found_and_not_retried() -> None:
	fake = Fake(http_error(404))
	with pytest.raises(ApiError) as err:
		make(fake).get('/x')
	assert (err.value.status, err.value.message) == (404, 'Test: not found')
	assert len(fake.requests) == 1


def test_other_http_errors_fail_at_once_as_502() -> None:
	fake = Fake(http_error(500))
	with pytest.raises(ApiError) as err:
		make(fake).get('/x')
	assert err.value.status == 502
	assert len(fake.requests) == 1


def test_rate_limit_is_retried_after_the_backoff() -> None:
	fake = Fake(http_error(429), ok({'ok': True}))
	assert make(fake, backoff=60.0).get('/x') == {'ok': True}
	assert 60.0 in fake.sleeps


def test_rate_limit_gives_up_after_the_retries_with_status_429() -> None:
	fake = Fake(*[http_error(429) for _ in range(4)])
	with pytest.raises(ApiError) as err:
		make(fake, retries=3, backoff=60.0).get('/x')
	assert err.value.status == 429
	assert len(fake.requests) == 4
	assert fake.sleeps.count(60.0) == 3


def test_an_empty_body_counts_as_the_rate_limit() -> None:
	fake = Fake(Response(b''), ok({'ok': 1}))
	assert make(fake).get('/x') == {'ok': 1}


def test_an_empty_body_that_never_goes_away_is_a_502() -> None:
	fake = Fake(*[Response(b'') for _ in range(4)])
	with pytest.raises(ApiError) as err:
		make(fake).get('/x')
	assert err.value.status == 502


def test_exponential_backoff_doubles() -> None:
	fake = Fake(http_error(503), http_error(503), ok({}))
	make(fake, backoff=2.0, exponential=True, retry_codes=(503,), interval=0.0).get('/x')
	assert [s for s in fake.sleeps if s >= 2.0] == [2.0, 4.0]


def test_only_configured_codes_are_retried() -> None:
	fake = Fake(http_error(503))
	with pytest.raises(ApiError) as err:
		make(fake, retry_codes=(429,)).get('/x')
	assert err.value.status == 502


def test_network_errors_are_502() -> None:
	fake = Fake(OSError('boom'))
	with pytest.raises(ApiError) as err:
		make(fake).get('/x')
	assert err.value.status == 502
	assert 'boom' in err.value.message


def test_get_bytes_limits_the_size() -> None:
	assert make(Fake(Response(b'abc'))).get_bytes('http://i/x', 10) == b'abc'
	with pytest.raises(ApiError, match='too large'):
		make(Fake(Response(b'x' * 11))).get_bytes('http://i/x', 10)
	with pytest.raises(ApiError) as err:
		make(Fake(OSError('down'))).get_bytes('http://i/x', 10)
	assert err.value.status == 502


def test_discogs_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(discogs, '_key', lambda: '')
	with pytest.raises(ApiError) as err:
		discogs.get('/releases/1')
	assert err.value.status == 400


def test_discogs_sends_the_key_and_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
	fake = Fake(ok({'id': 1}))
	monkeypatch.setattr(
		discogs,
		'api',
		RateLimitedApi(
			name='Discogs',
			base='https://api.discogs.com',
			headers=discogs.api.headers,
			interval=0.0,
			opener=fake.opener,
			sleep=fake.sleep,
			clock=fake.clock,
		),
	)
	monkeypatch.setattr(discogs, '_key', lambda: 'SECRET')
	assert discogs.get('/releases/1') == {'id': 1}
	req = fake.requests[0]
	assert req.get_header('Authorization') == 'Discogs token=SECRET'
	assert req.get_header('User-agent').startswith('Tagwright/')
