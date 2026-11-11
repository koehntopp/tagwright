"""The Discogs API (ADR 0013): one shared, rate-limited client for the web layer and the pipeline.

Discogs allows 60 requests a minute, so requests are one at a time, 1.1 s apart, with a 5 s pause when
X-Discogs-Ratelimit-Remaining drops below 3. A 429 or an empty body is retried 3 times after 60 s.
"""

from collections.abc import Callable

from pipeline.http import ApiError, RateLimitedApi


def _no_key() -> str:
	return ''


_key: Callable[[], str] = (
	_no_key  # replaced by configure(); a callable so settings changes apply at once
)

api = RateLimitedApi(
	name='Discogs',
	base='https://api.discogs.com',
	headers=lambda: {'User-Agent': 'Tagwright/0.2', 'Authorization': f'Discogs token={_key()}'},
	interval=1.1,
	low_header='X-Discogs-Ratelimit-Remaining',
)


def configure(key: Callable[[], str]) -> None:
	"""Set where the API key comes from (the settings); called once at start-up."""
	global _key
	_key = key


def get(path: str, **params: str | int) -> dict:
	if not _key():
		raise ApiError(400, 'Discogs API key not set (Settings)')
	return api.get(path, **params)


def image(url: str) -> bytes:
	"""A release image, at most 20 MB."""
	return api.get_bytes(url, 20_000_000)
