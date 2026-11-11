"""One rate-limited JSON API client for Discogs, MusicBrainz and lrclib (ADR 0036, 0013, 0023).

Requests are sent one at a time, at least `interval` seconds apart, and the waits are shared (the lock is
held), so concurrent callers do not pause and then burst together. A rate-limit answer (or an empty body,
which is how Discogs sometimes signals the limit) is retried after `backoff` seconds; other errors fail at
once with a status the web layer can pass on.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

log = logging.getLogger(__name__)


class ApiError(Exception):
	"""A failed API call; `status` is the HTTP status the web layer should answer with."""

	def __init__(self, status: int, message: str) -> None:
		super().__init__(message)
		self.status = status
		self.message = message


@dataclass
class RateLimitedApi:
	name: str  # shown in error messages ('Discogs')
	base: str
	headers: Callable[
		[], dict[str, str]
	]  # evaluated per request, so a changed API key is picked up
	interval: float  # minimum seconds between two requests
	retries: int = 3
	backoff: float = 60.0  # seconds before a retry
	exponential: bool = False  # backoff, 2 * backoff, 4 * backoff ...
	retry_codes: tuple[int, ...] = (429,)
	low_header: str = ''  # response header with the remaining request budget ('' = none)
	low_threshold: int = 3
	low_pause: float = 5.0
	timeout: float = 20.0
	last: float = 0.0  # time the last request ended; guarded by lock
	lock: threading.Lock = field(default_factory=threading.Lock)
	# Replaced in tests so no real network or waiting is involved.
	opener: Callable[..., Any] = urllib.request.urlopen
	sleep: Callable[[float], None] = time.sleep
	clock: Callable[[], float] = time.time

	def _wait(self) -> None:
		self.sleep(max(0.0, self.interval - (self.clock() - self.last)))

	def _done(self, headers: Mapping[str, str] | None) -> None:
		self.last = self.clock()
		remaining = headers.get(self.low_header) if headers and self.low_header else None
		if remaining and remaining.isdigit() and int(remaining) < self.low_threshold:
			self.sleep(self.low_pause)

	def get(self, path: str, **params: str | int) -> dict:
		"""GET base + path with the query parameters; the parsed JSON object."""
		url = self.base + path + ('?' + urlencode(params) if params else '')
		req = urllib.request.Request(url, headers=self.headers())
		with self.lock:
			for attempt in range(self.retries + 1):
				self._wait()
				try:
					with self.opener(req, timeout=self.timeout) as r:
						data = json.load(r)
						self._done(r.headers)
					return data
				except urllib.error.HTTPError as e:
					self._done(e.headers)
					if e.code == 404:
						raise ApiError(404, f'{self.name}: not found') from e
					if e.code not in self.retry_codes:
						raise ApiError(502, f'{self.name}: HTTP {e.code}') from e
					err = ApiError(429, f'{self.name} rate limit reached; try again in a minute')
				except json.JSONDecodeError:
					self._done(None)
					err = ApiError(
						502, f'{self.name} sent an empty response; try again in a minute'
					)
				except OSError as e:
					self._done(None)
					raise ApiError(502, f'{self.name}: {e}') from e
				if attempt < self.retries:
					wait = self.backoff * (2**attempt if self.exponential else 1)
					log.warning(
						'%s API error (%s), waiting %.0f s (attempt %d/%d)',
						self.name,
						err.message,
						wait,
						attempt + 1,
						self.retries,
					)
					self.sleep(wait)
				else:
					raise err
		raise AssertionError('unreachable')  # the loop returns or raises

	def get_bytes(self, url: str, limit: int) -> bytes:
		"""Download a file (an image) with the same pacing; more than `limit` bytes is an error."""
		req = urllib.request.Request(url, headers=self.headers())
		with self.lock:
			self._wait()
			try:
				with self.opener(req, timeout=30) as r:
					data = r.read(limit + 1)
					self._done(r.headers)
			except OSError as e:
				self._done(None)
				raise ApiError(502, f'{self.name} download: {e}') from e
		if len(data) > limit:
			raise ApiError(502, f'{self.name} download is too large')
		return data
