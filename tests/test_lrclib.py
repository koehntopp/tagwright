"""lrclib request pacing, retries and the circuit breaker (ADR 0021, 0036), carried over from update_lyrics.py."""

import logging

import pytest

from pipeline import lrclib

from .test_http import Fake, Response, http_error, ok


def pacer(fake: Fake) -> lrclib.Pacer:
	return lrclib.Pacer(clock=fake.clock, sleep=fake.sleep)


class TestPacer:
	def test_the_first_request_does_not_wait(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.acquire()
		assert fake.sleeps == []

	def test_the_next_request_waits_the_interval_plus_jitter(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.acquire()
		p.release()
		p.acquire()
		assert (
			lrclib.BASE_INTERVAL <= fake.sleeps[0] <= lrclib.BASE_INTERVAL + lrclib.REQUEST_JITTER
		)

	def test_a_rate_limit_doubles_the_interval_up_to_the_maximum(self) -> None:
		fake = Fake()
		p = pacer(fake)
		seen = []
		for _ in range(8):
			fake.now += 100  # every request starts after the previous raise
			interval, raised = p.failure(fake.now, rate_limited=True)
			seen.append((interval, raised))
		assert [i for i, _ in seen[:5]] == [1.0, 2.0, 4.0, 8.0, 8.0]
		assert [r for _, r in seen[:5]] == [True, True, True, True, False]

	def test_a_request_that_started_before_the_last_raise_cannot_raise_again(self) -> None:
		fake = Fake()
		p = pacer(fake)
		started = fake.now
		fake.now += 5
		assert p.failure(started, rate_limited=True) == (1.0, True)
		assert p.failure(started, rate_limited=True) == (1.0, False)  # same batch of requests

	def test_a_429_without_retry_after_waits_the_default(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.failure(fake.now, rate_limited=True)
		p.acquire()
		assert fake.sleeps[0] >= lrclib.DEFAULT_RETRY_AFTER

	def test_retry_after_is_capped(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.failure(fake.now, retry_after=10_000)
		p.acquire()
		assert lrclib.MAX_RETRY_AFTER <= fake.sleeps[0] <= lrclib.MAX_RETRY_AFTER + 1

	def test_other_failures_do_not_widen_the_interval(self) -> None:
		fake = Fake()
		p = pacer(fake)
		assert p.failure(fake.now) == (lrclib.BASE_INTERVAL, False)

	def test_successes_shrink_a_widened_interval_again(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.failure(fake.now, rate_limited=True)  # 1.0
		relaxed = [p.success() for _ in range(lrclib.RELAX_AFTER)]
		assert relaxed[-1] == (0.75, True)
		assert all(not r for _, r in relaxed[:-1])
		for _ in range(lrclib.RELAX_AFTER * 3):
			p.success()
		assert p.success()[0] == lrclib.BASE_INTERVAL  # never below the base

	def test_the_circuit_opens_after_repeated_failures_without_a_success(self) -> None:
		fake = Fake()
		p = pacer(fake)
		for _ in range(lrclib.DOWN_AFTER):
			p.failure(fake.now)
		assert not p.is_down()  # not yet: a success was seen recently
		fake.now += lrclib.DOWN_WINDOW
		assert p.is_down()
		assert p.report_down_once() is True
		assert p.report_down_once() is False

	def test_a_success_resets_the_failure_streak(self) -> None:
		fake = Fake()
		p = pacer(fake)
		for _ in range(lrclib.DOWN_AFTER - 1):
			p.failure(fake.now)
		p.success()
		p.failure(fake.now)
		fake.now += lrclib.DOWN_WINDOW * 2
		assert not p.is_down()

	def test_rejected_credentials_open_the_circuit_and_are_reported_once(self) -> None:
		p = pacer(Fake())
		assert p.reject_credentials() is True
		assert p.reject_credentials() is False
		assert p.is_down()

	def test_close_circuit_lets_a_retry_round_probe_again(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.reject_credentials()
		for _ in range(lrclib.DOWN_AFTER):
			p.failure(fake.now)
		fake.now += lrclib.DOWN_WINDOW
		p.report_down_once()
		p.close_circuit()
		assert not p.is_down()
		assert p.report_down_once() is False  # not down any more
		assert p.failure(fake.now)[0] == lrclib.BASE_INTERVAL  # the learned interval is kept


PARAMS = {'artist_name': 'A', 'track_name': 'T', 'duration': '10'}


def call(fake: Fake, p: lrclib.Pacer | None = None) -> dict | None:
	return lrclib.get(p or pacer(fake), PARAMS, opener=fake.opener, sleep=fake.sleep)


class TestGet:
	def test_200_is_the_json_body_with_identifying_headers(self) -> None:
		fake = Fake(ok({'syncedLyrics': 'x'}))
		assert call(fake) == {'syncedLyrics': 'x'}
		req = fake.requests[0]
		assert req.full_url.startswith(lrclib.LRCLIB_GET_URL + '?artist_name=A&track_name=T')
		assert req.get_header('User-agent').startswith('Tagwright/')
		assert req.get_header('Lrclib-app-id') == lrclib.LRCLIB_APP_ID

	def test_404_means_not_found_and_counts_as_an_answer(self) -> None:
		fake = Fake(http_error(404))
		assert call(fake) == {}

	def test_401_is_logged_once_and_not_retried(self, caplog: pytest.LogCaptureFixture) -> None:
		fake = Fake(http_error(401), http_error(401))
		p = pacer(fake)
		with caplog.at_level(logging.ERROR):
			assert call(fake, p) is None
			assert call(fake, p) is None  # the circuit is open: no second request
		assert len(fake.requests) == 1
		assert caplog.text.count('rejected the Lrclib-App-Id') == 1

	def test_a_429_is_retried_after_retry_after_and_slows_the_pacing(
		self, caplog: pytest.LogCaptureFixture
	) -> None:
		fake = Fake(http_error(429, {'Retry-After': '2'}), ok({'ok': 1}))
		p = pacer(fake)
		with caplog.at_level(logging.WARNING):
			assert call(fake, p) == {'ok': 1}
		assert max(fake.sleeps) >= 2  # Retry-After honoured
		assert 'rate limit hit' in caplog.text

	def test_a_503_with_retry_after_is_honoured(self) -> None:
		fake = Fake(http_error(503, {'Retry-After': '3'}), ok({'ok': 1}))
		assert call(fake) == {'ok': 1}
		assert max(fake.sleeps) >= 3

	def test_a_server_error_is_retried_with_a_growing_backoff(self) -> None:
		fake = Fake(http_error(500), http_error(500), ok({'ok': 1}))
		assert call(fake) == {'ok': 1}
		backoffs = [s for s in fake.sleeps if s >= lrclib.RETRY_BACKOFF]
		assert backoffs[0] < backoffs[1]  # 1 s, then 2 s (each with jitter)

	def test_it_gives_up_after_the_attempts_with_none(self) -> None:
		fake = Fake(*[http_error(500) for _ in range(lrclib.MAX_ATTEMPTS)])
		assert call(fake) is None
		assert len(fake.requests) == lrclib.MAX_ATTEMPTS

	def test_network_errors_and_broken_json_count_as_failures(self) -> None:
		fake = Fake(OSError('down'), Response(b'not json'), ok({'ok': 1}))
		assert call(fake) == {'ok': 1}

	def test_an_open_circuit_returns_none_without_a_request(self) -> None:
		fake = Fake()
		p = pacer(fake)
		p.reject_credentials()
		assert call(fake, p) is None
		assert fake.requests == []

	def test_the_circuit_opening_ends_the_attempts(self, caplog: pytest.LogCaptureFixture) -> None:
		fake = Fake(*[http_error(500) for _ in range(lrclib.MAX_ATTEMPTS)])
		p = pacer(fake)
		for _ in range(lrclib.DOWN_AFTER - 1):
			p.failure(fake.now)
		fake.now += lrclib.DOWN_WINDOW
		with caplog.at_level(logging.WARNING):
			assert call(fake, p) is None
		assert len(fake.requests) == 1
		assert 'looks down' in caplog.text
