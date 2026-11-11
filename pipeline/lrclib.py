"""lrclib.net lookups for the lyrics step (ADR 0021, 0036): request pacing and the `get` call.

lrclib asks clients to identify themselves and to send requests one at a time. Registered applications get
higher rate limits (about 90 requests/min per IP with a User-Agent alone, 180/min with a registered
Lrclib-App-Id). The app id is a public header ("not a secret, so it is safe to ship in a client"); the
secret Lrclib-Api-Key is not used. An invalid value is rejected with 401 Unauthorized.
"""

import json
import logging
import random
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

log = logging.getLogger(__name__)

USER_AGENT = 'Tagwright/0.2 (+https://github.com/koehntopp/tagwright)'
LRCLIB_APP_ID = 'Nm2UKEDqSxmkysVsuRQhjw9hWSYkbleD8mGFP7WcBOo'


def headers() -> dict[str, str]:
	"""Headers identifying this application on every lrclib.net request."""
	return {'User-Agent': USER_AGENT, 'Lrclib-App-Id': LRCLIB_APP_ID}


LRCLIB_GET_URL = 'https://lrclib.net/api/get'
MAX_ATTEMPTS = 4  # per request; the shared Pacer spaces the attempts
MAX_RETRY_AFTER = 300.0
# Spacing like the official client (lrcget): wait BASE_INTERVAL plus up to REQUEST_JITTER after
# each response, about 85 requests/min with latency. No burst: bursts provoked 429s (ADR 0007 s.4).
BASE_INTERVAL = 0.5
REQUEST_JITTER = 0.25
DEFAULT_RETRY_AFTER = 1.0  # a 429 without Retry-After, as lrcget treats it
RETRY_BACKOFF = 1.0  # seconds before the 2nd attempt after a 5xx/network error; doubles each time
MAX_INTERVAL = 8.0
RELAX_AFTER = 10  # consecutive successes before the interval shrinks again
DOWN_AFTER = 5  # failures in a row, with no success for DOWN_WINDOW seconds, open the circuit
DOWN_WINDOW = 60.0
# (cool-down seconds, workers) for each pass over tracks that lrclib failed to answer
RETRY_ROUNDS = ((30, 2), (60, 2))


class Pacer:
	"""Shared request pacing: one request in flight at a time.

	lrclib asks clients to send requests sequentially. Each request starts `interval` (plus up to
	REQUEST_JITTER) after the previous one finished. A 429 (a real rate limit) doubles the interval
	and every run of successes shrinks it again, so it settles at whatever rate lrclib tolerates.
	5xx and network errors do not change the pacing.
	"""

	def __init__(
		self,
		clock: Callable[[], float] = time.monotonic,
		sleep: Callable[[float], None] = time.sleep,
	) -> None:
		self._clock = clock
		self._sleep = sleep
		self._lock = threading.Lock()
		self._slot = threading.Semaphore(1)
		self._interval = BASE_INTERVAL
		self._next_start = 0.0
		self._floor_until = 0.0  # Retry-After: no request may start before this
		self._raised_at = 0.0
		self._successes = 0
		self._fail_streak = 0
		self._last_success = self._clock()
		self._down_reported = False
		self._auth_failed = False
		self._auth_reported = False

	def acquire(self) -> float:
		"""Wait for the single request slot and for the next start time; return the start time.

		Every acquire() must be paired with a release() once the request has finished.
		"""
		self._slot.acquire()
		with self._lock:
			now = self._clock()
			start = max(now, self._next_start, self._floor_until)
		if start > now:
			self._sleep(start - now)
		return start

	def release(self) -> None:
		with self._lock:
			gap = self._interval + random.uniform(0, REQUEST_JITTER)
			self._next_start = max(self._next_start, self._clock() + gap)
		self._slot.release()

	def failure(
		self,
		started_at: float,
		retry_after: float | None = None,
		rate_limited: bool = False,
	) -> tuple[float, bool]:
		"""Record a failed request; return (interval, whether this raised it).

		Only a rate limit (429) widens the interval; other failures just count towards the
		circuit breaker. A request that started before the last raise cannot escalate it again.
		"""
		with self._lock:
			now = self._clock()
			self._successes = 0
			self._fail_streak += 1
			raised = False
			if rate_limited and started_at > self._raised_at and self._interval < MAX_INTERVAL:
				self._interval = min(self._interval * 2, MAX_INTERVAL)
				self._raised_at = now
				self._next_start = max(self._next_start, now + self._interval)
				raised = True
			if rate_limited and retry_after is None:
				retry_after = DEFAULT_RETRY_AFTER
			if retry_after is not None:
				self._floor_until = max(self._floor_until, now + min(retry_after, MAX_RETRY_AFTER))
			return self._interval, raised

	def success(self) -> tuple[float, bool]:
		"""Record a good answer; return (interval, whether this relaxed it)."""
		with self._lock:
			self._fail_streak = 0
			self._last_success = self._clock()
			self._successes += 1
			relaxed = False
			if self._successes >= RELAX_AFTER and self._interval > BASE_INTERVAL:
				self._interval = max(BASE_INTERVAL, self._interval * 0.75)
				self._successes = 0
				relaxed = True
			return self._interval, relaxed

	def is_down(self) -> bool:
		"""True after DOWN_AFTER failures in a row with no success for DOWN_WINDOW seconds,
		or once lrclib has rejected the app id (retrying cannot help)."""
		with self._lock:
			return self._auth_failed or (
				self._fail_streak >= DOWN_AFTER
				and self._clock() - self._last_success >= DOWN_WINDOW
			)

	def reject_credentials(self) -> bool:
		"""Record a 401; True only the first time, so the error is logged once."""
		with self._lock:
			first = not self._auth_reported
			self._auth_failed = True
			self._auth_reported = True
			return first

	def report_down_once(self) -> bool:
		"""True the first time it is called while the circuit is open (for one log line)."""
		if not self.is_down():
			return False
		with self._lock:
			first = not self._down_reported
			self._down_reported = True
			return first

	def close_circuit(self) -> None:
		"""Forget the failure streak before a retry round; keep the learned interval."""
		with self._lock:
			self._fail_streak = 0
			self._last_success = self._clock()
			self._down_reported = False
			self._auth_failed = False  # a retry round probes once more
			self._floor_until = 0.0


def get(
	pacer: Pacer,
	params: dict[str, str],
	opener: Callable[..., Any] = urllib.request.urlopen,
	sleep: Callable[[float], None] = time.sleep,
) -> dict | None:
	"""One lrclib lookup: the JSON body on 200, {} on 404, None if lrclib kept failing."""
	reason = ''
	if pacer.is_down():
		return None  # circuit open: defer to the retry rounds instead of waiting again
	url = LRCLIB_GET_URL + '?' + urlencode(params)
	for attempt in range(MAX_ATTEMPTS):
		started_at = pacer.acquire()
		retry_after = None
		rate_limited = False
		try:
			try:
				with opener(urllib.request.Request(url, headers=headers()), timeout=10) as response:
					body = json.load(response)
				interval, relaxed = pacer.success()
				if relaxed:
					log.info('lrclib is answering again; one request per %.1f s', interval)
				return body
			except urllib.error.HTTPError as e:
				if e.code == 401:
					if pacer.reject_credentials():
						log.error('lrclib rejected the Lrclib-App-Id header (401)')
					return None
				if e.code == 404:
					pacer.success()
					return {}
				reason = f'HTTP {e.code}'
				rate_limited = e.code == 429
				header = e.headers.get('Retry-After') if e.headers else None
				if e.code in (429, 503) and header and header.replace('.', '', 1).isdigit():
					# lrclib requires honoring Retry-After plus up to 30% random jitter
					retry_after = float(header) * (1 + random.uniform(0, 0.3))
			except (OSError, json.JSONDecodeError) as e:
				reason = type(e).__name__
		finally:
			pacer.release()
		interval, raised = pacer.failure(started_at, retry_after, rate_limited)
		if raised:
			log.warning(
				'lrclib rate limit hit (%s); slowing to one request per %.1f s', reason, interval
			)
		if pacer.report_down_once():
			log.warning('lrclib looks down; deferring the remaining tracks to the retry rounds')
		if pacer.is_down():
			break
		if not rate_limited and retry_after is None and attempt < MAX_ATTEMPTS - 1:
			# 5xx / network error: plain backoff, the pacing interval stays as it is
			sleep(RETRY_BACKOFF * 2**attempt * (1 + random.uniform(0, 0.3)))
	return None
