"""Step 5, lyrics: LRC or plain lyrics from lrclib.net into the LYRICS tag (ADR 0006, 0021, 0036).

For every track of an album that has a DISCOGS_RELEASE_ID (read from the first file of each folder) the step
decides one of: leave it, fix what is there (headers, typography, capitalization), mark it instrumental, or
fetch new lyrics. An existing synced LRC is never replaced by another source. lrclib is asked one request at a
time (see `pipeline/lrclib.py`); a track lrclib did not answer is left untouched and retried in later rounds.

Not carried over from the discogs `update_lyrics.py`: the export of every track's lyrics to `{id}_{track}.lrc|txt`
files in a `lyrics/` cache folder and its pruning. Tagwright reads and writes the tag only.
"""

import logging
import re
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from mutagen import MutagenError
from mutagen.flac import FLAC

from pipeline import lrclib
from pipeline.layout import flacs
from pipeline.lrc_format import (
	apply_headers,
	capitalize_lrc,
	capitalize_txt,
	has_manual_instrumental_marker,
	is_instrumental_marker,
	is_invalid_lrc,
	is_lrc,
	make_instrumental_lrc,
	normalize_lrc_text,
	normalize_text,
	resolve_artist,
)
from pipeline.tagio import touch
from pipeline.tools import Context

log = logging.getLogger(__name__)

MAX_WORKERS = 8
LANGUAGE_TAG = 'LYRICS_LANGUAGE'  # written by the Discogs tags step from MusicBrainz (ADR 0023)
INSTRUMENTAL_LANGUAGE = 'zxx'  # ISO 639-3 "no linguistic content"
TRAILING_BRACKET_RE = re.compile(r'\s*[\(\[][^()\[\]]*[\)\]]\s*$')
REPORT_EVERY = 5.0  # seconds between progress lines

type Lookup = Callable[
	[dict[str, str]], dict | None
]  # lrclib params -> body, {} for 404, None for "no answer"


def strip_trailing_bracket(title: str) -> str:
	"""Strip one trailing (...)/[...] group, e.g. '(Live at Wembley)'."""
	return TRAILING_BRACKET_RE.sub('', title).strip()


def is_instrumental_language(values: list[str]) -> bool:
	"""Does MusicBrainz call the track an instrumental? Only a lone `zxx` counts: `zxx` next to a real
	language, `mul`, `und` or no tag say nothing."""
	return [str(v).strip().lower() for v in values] == [INSTRUMENTAL_LANGUAGE]


@dataclass
class Result:
	"""What to do with one track. `action`: new, fix, skip, error (unreadable or untagged) or failed (lrclib
	did not answer: nothing is written for the track). `kind`: lrc, txt, instrumental or none."""

	path: Path
	artist: str = ''
	title: str = ''
	lyrics: str = ''
	kind: str = 'none'
	action: str = 'skip'
	discogs_id: str = ''
	track: str = ''


def first(tags: Mapping[str, list[str]], key: str) -> str:
	values = tags.get(key)
	return str(values[0]) if values else ''


def search_params(
	artist: str, track_artist: str, title: str, album: str, duration: str
) -> list[dict[str, str]]:
	"""The lookups to try, in order: for each artist (ALBUMARTIST, then the track's own ARTIST when it differs:
	compilations and soundtracks have a "Various Artists" album artist lrclib does not know) and each track name
	(the full title, then without a trailing bracket), the search with the album name, then without."""
	stripped = strip_trailing_bracket(title)
	names = [title] if stripped == title else [title, stripped]
	artists = [artist] if not track_artist or track_artist == artist else [artist, track_artist]
	return [
		v
		for artist_name in artists
		for track_name in names
		for v in (
			{
				'artist_name': artist_name,
				'track_name': track_name,
				'album_name': album,
				'duration': duration,
			},
			{'artist_name': artist_name, 'track_name': track_name, 'duration': duration},
		)
	]


def fetch_one(path: Path, lookup: Lookup) -> Result:
	"""Read the tags of a file and decide what its lyrics should be."""
	if not path.is_file():
		return Result(path)
	try:
		song = FLAC(path)
		tags = song.tags or {}
		artist = resolve_artist(first(tags, 'ALBUMARTIST'), first(tags, 'ARTIST'))
		title = first(tags, 'TITLE')
		discogs_id = first(tags, 'DISCOGS_RELEASE_ID')
		track = first(tags, 'TRACKNUMBER')
		album = first(tags, 'ALBUM')
		existing = first(tags, 'LYRICS').strip()
		instrumental_language = is_instrumental_language(list(tags.get(LANGUAGE_TAG) or []))
		track_artist = first(tags, 'ARTIST')
		length = float(song.info.length) if song.info and hasattr(song.info, 'length') else 0.0
	except (MutagenError, OSError) as e:
		log.warning('Could not read FLAC tags for %s: %s', path, e)
		return Result(path, action='error')

	def result(lyrics: str, kind: str, action: str) -> Result:
		return Result(path, artist, title, lyrics, kind, action, discogs_id, track)

	if not artist or not title:
		log.info('Missing ALBUMARTIST/ARTIST or TITLE tag in %s', path)
		return result('', 'none', 'error')

	if existing and is_instrumental_marker(existing):
		return result(existing, 'instrumental', 'skip')

	if existing and has_manual_instrumental_marker(existing):
		# An informal or incomplete instrumental marker: normalize it to the canonical block without asking
		# lrclib. A syntax fix, not new information, so it counts as 'fix'.
		return result(make_instrumental_lrc(artist, title, album, length), 'instrumental', 'fix')

	if instrumental_language and not is_lrc(existing):
		# MusicBrainz says the track has no vocals: no lrclib request (it can only return wrong lyrics for
		# it). Plain text is replaced; an existing LRC is left to the rule below.
		log.info(
			'Instrumental via %s=%s: %s - %s', LANGUAGE_TAG, INSTRUMENTAL_LANGUAGE, artist, title
		)
		return result(make_instrumental_lrc(artist, title, album, length), 'instrumental', 'new')

	if existing and is_lrc(existing):
		# An existing LRC is never replaced by another source (no lrclib request at all); it is only
		# corrected in place: headers, typographic characters and line capitalization.
		updated = capitalize_lrc(
			normalize_lrc_text(apply_headers(existing, artist, title, album, length))
		)
		return result(updated, 'lrc', 'fix' if updated != existing else 'skip')

	data: dict = {}
	found_via_stripped = False
	for params in search_params(artist, track_artist, title, album, str(round(length))):
		body = lookup(params)
		if body is None:
			# lrclib is throttling or down, which is not the same as "not found": stop probing further
			# variants and never write or remove anything for this track.
			return result('', 'none', 'failed')
		if body:
			data = body
			found_via_stripped = params['track_name'] != title
			break
	if found_via_stripped:
		log.info(
			"Lyrics found via stripped title '%s' (original: '%s')",
			strip_trailing_bracket(title),
			title,
		)

	if data.get('instrumental'):
		marker = make_instrumental_lrc(artist, title, album, length)
		return result(
			existing if marker == existing else marker,
			'instrumental',
			'skip' if marker == existing else 'new',
		)

	if data.get('syncedLyrics'):
		lrc = re.sub(r'\[(\d{2}:\d{2}\.\d{2})\d\]', r'[\1]', data['syncedLyrics'])
		if is_invalid_lrc(lrc):
			log.warning('Invalid LRC timestamps from lrclib, skipping: %s (%s)', title, artist)
		else:
			lrc = capitalize_lrc(
				normalize_lrc_text(apply_headers(lrc, artist, title, album, length))
			)
			return result(
				existing if lrc == existing else lrc, 'lrc', 'skip' if lrc == existing else 'new'
			)
	if data.get('plainLyrics') and not existing:
		return result(capitalize_txt(normalize_text(data['plainLyrics'])), 'txt', 'new')

	# Nothing new fetched: keep what is on disk (only plain text reaches this point), normalizing characters
	# and capitalization if needed.
	if existing:
		fixed = capitalize_txt(normalize_text(existing))
		return result(
			fixed if fixed != existing else existing, 'txt', 'fix' if fixed != existing else 'skip'
		)

	log.warning(
		"No lyrics found at lrclib: '%s' (artist searched: '%s', album: '%s')", title, artist, album
	)
	return result('', 'none', 'skip')


def collect_tracks(album: Path) -> list[Path]:
	"""Every FLAC of the folders whose first file has a numeric DISCOGS_RELEASE_ID (each folder is judged by itself)."""
	by_dir: dict[Path, list[Path]] = {}
	for f in flacs(album):
		by_dir.setdefault(f.parent, []).append(f)
	tracks: list[Path] = []
	for files in by_dir.values():
		try:
			int(first(FLAC(files[0]).tags or {}, 'DISCOGS_RELEASE_ID'))
		except ValueError, TypeError, MutagenError, OSError:
			continue
		tracks.extend(files)
	return tracks


def write_lyrics(result: Result, stats: dict[str, int]) -> None:
	"""Count one finished track and write its lyrics into the FLAC tag when they are new or fixed."""
	stats[
		{'lrc': 'lrc', 'txt': 'txt', 'instrumental': 'instrumental'}.get(result.kind, 'none')
	] += 1
	if result.action not in ('new', 'fix'):
		return
	stats['new' if result.action == 'new' else 'fixed'] += 1
	try:
		audio = FLAC(result.path)  # reopened: tags may have been written since the lookup started
		if audio.tags is None:
			audio.add_tags()
		audio['LYRICS'] = [result.lyrics]
		audio.save()
		touch(result.path)
	except (MutagenError, OSError) as e:
		log.error('Could not save lyrics for %s: %s', result.path, e)
		return
	who = f'{result.title} ({result.artist})'
	if result.kind == 'instrumental':
		log.info('Instrumental track marked: %s', who)
	elif result.action == 'fix':
		log.info('Lyrics fixed: %s', who)
	else:
		log.info('%s lyrics added: %s', 'LRC' if result.kind == 'lrc' else 'TXT', who)


RETRY_ROUNDS = lrclib.RETRY_ROUNDS


def run(
	album: Path,
	ctx: Context,
	lookup: Lookup | None = None,
	retry_rounds: tuple[tuple[float, int], ...] = RETRY_ROUNDS,
) -> None:
	"""Fetch, fix and write the lyrics of an album. `lookup` is replaced in tests (no network)."""
	pacer = lrclib.Pacer()
	lookup = lookup or partial(lrclib.get, pacer)
	tracks = collect_tracks(album)
	log.info(
		'Fetching lyrics for %d tracks with %d workers (lrclib requests go one at a time)',
		len(tracks),
		MAX_WORKERS,
	)
	stats = dict.fromkeys(('lrc', 'txt', 'none', 'instrumental', 'new', 'fixed', 'failed'), 0)
	state = {'last_report': time.monotonic(), 'done': 0}
	failed_info: dict[Path, Result] = {}

	def handle(result: Result | None, path: Path, first_pass: bool) -> None:
		if result is not None and result.action == 'failed':
			if first_pass:
				stats['failed'] += (
					1  # lrclib did not answer: nothing is written or removed for this track
				)
			failed_info[path] = result
		elif result is not None:
			if not first_pass:
				stats['failed'] -= 1  # recovered in a retry pass
			failed_info.pop(path, None)
			write_lyrics(result, stats)
		if first_pass:
			state['done'] += 1
			if time.monotonic() - state['last_report'] >= REPORT_EVERY:
				state['last_report'] = time.monotonic()
				log.info('Progress: %d/%d tracks - %s', state['done'], len(tracks), summary(stats))

	def one_pass(paths: list[Path], workers: int, first_pass: bool) -> list[Path]:
		failed: list[Path] = []
		with ThreadPoolExecutor(max_workers=workers) as executor:
			futures: dict[Future[Result], Path] = {
				executor.submit(fetch_one, p, lookup): p for p in paths
			}
			try:
				for future in as_completed(futures):
					ctx.check()
					path = futures[future]
					try:
						result = future.result()
					except (MutagenError, OSError, ValueError) as e:
						log.error('Fetch error: %s', e)
						handle(None, path, first_pass)
						continue
					if result.action == 'failed':
						failed.append(path)
					handle(result, path, first_pass)
			except BaseException:
				executor.shutdown(wait=False, cancel_futures=True)
				raise
		return failed

	failed = one_pass(tracks, MAX_WORKERS, True)
	for cooldown, workers in retry_rounds:
		if not failed:
			break
		log.warning(
			'%d tracks got no answer from lrclib; retrying in %s s with %d workers',
			len(failed),
			cooldown,
			workers,
		)
		ctx.stop.wait(cooldown)
		ctx.check()
		pacer.close_circuit()
		failed = one_pass(failed, workers, False)

	for path in failed:
		info = failed_info.get(path)
		log.warning(
			'Lyrics not fetched, lrclib unavailable: %s - %s (%s)',
			info.artist if info else '',
			info.title if info else '',
			path,
		)
	log.info('Done - %s', summary(stats))


def summary(stats: dict[str, int]) -> str:
	return (
		f'LRC: {stats["lrc"]} TXT: {stats["txt"]} None: {stats["none"]} Instrumental: {stats["instrumental"]} '
		f'New: {stats["new"]} Fixed: {stats["fixed"]} Failed: {stats["failed"]}'
	)
