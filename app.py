#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = ["fastapi", "uvicorn", "mutagen", "python-slugify", "unidecode", "pathvalidate", "pillow"]
# ///
"""Tagwright: web UI and the fix pipeline for FLAC albums (the pipeline is the package pipeline/).

Env, all three required (no default paths, ADR 0055): STAGING_FOLDER, LIBRARY_FOLDER, DATA_DIR (settings).
PORT (default 8080). The pipeline is the package pipeline/ (ADR 0036).
"""

import csv
import io
import json
import logging
import os
import re
import shutil
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Iterable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from starlette.types import Scope

from library import planner as lib_planner
from library.scanner import read_tags
from library.summaries import SummaryStore
from library.template import INDEXED_TAGS, PALETTE, MissingTag, Template, render_level
from library.template import default as default_template
from library.template import validate as validate_template
from library.watcher import Library
from library.watcher import Settings as LibrarySettings
from pipeline import covers, layout, logconfig, lrclib
from pipeline import discogs as discogs_api
from pipeline import musicbrainz as mb_api
from pipeline.audio import Audio, Cover, is_audio, new_cover, open_audio
from pipeline.config import Config
from pipeline.fixtags import DISCOGS_TAG_PREFIXES, fix_album
from pipeline.http import ApiError
from pipeline.layout import album_dirs, flacs, is_disc_dir
from pipeline.naming import bliss_album, rename_files
from pipeline.run import only_steps, run_album
from pipeline.tagio import Tags, channels_from_title, tag
from pipeline.tools import Context, Stopped


def env_path(name: str) -> Path:
	"""Read a required path from the environment; ~ is expanded, a missing or relative path is a startup error."""
	if not os.environ.get(name):
		raise SystemExit(f'{name} is not set: give it as an absolute path')
	p = Path(os.environ[name]).expanduser()
	if not p.is_absolute():
		raise SystemExit(f'{name}={p} must be an absolute path (missing leading slash?)')
	return p.resolve()


ROOT = env_path('STAGING_FOLDER')
INGEST = env_path('LIBRARY_FOLDER')
layout.STAGING = ROOT
DATA = env_path('DATA_DIR')  # settings.json, library.db, the MusicBrainz cache
SETTINGS_FILE = DATA / 'settings.json'
log = logging.getLogger('app')  # the program's own lines (ADR 0064)
applog = log  # the same logger, for functions that have a local list called `log`
KEYS = ('discogs_api_key',)
settings: dict = {}
if SETTINGS_FILE.is_file():
	settings = json.loads(SETTINGS_FILE.read_text())
CATALOG_KEYS = (
	'CATALOGNUMBER',
	'CATALOG NUMBER',
	'CATALOG_NUMBER',
	'CATALOGNO',
)  # spellings fixtags reads, first present wins
# One entry per required tag (alternative spellings together); an empty one means the album is not ready.
REQUIRED_TAGS = (
	('ARTIST',),
	('ALBUMARTIST',),
	('TITLE',),
	('ALBUM',),
	('TRACKNUMBER',),
	('DISCNUMBER',),
	('ALBUM_FORMAT',),
	CATALOG_KEYS,
)
MIN_COVER = int(
	settings.get('min_cover', 1400)
)  # px, either side; a smaller or missing cover blocks the album; 0 turns the check off
MAX_COVER = int(
	settings.get('max_cover', 1500)
)  # px, either side; a larger cover is scaled down when it is uploaded, fetched or by a run (ADR 0074)


def app_config() -> Config:
	"""The pipeline's configuration with the settings that reach it."""
	return Config(data_dir=DATA, cover_max_size=MAX_COVER)


def cover_note(cov: dict | None) -> str:
	return (
		f'Cover is {cov["w"]}x{cov["h"]}, below the minimum {MIN_COVER}x{MIN_COVER}.'
		if cov
		else 'The album has no cover.'
	)


SYNCED_RE = re.compile(r'\[\d{2}:\d{2}\.\d{2}\]')  # strict [MM:SS.xx], as in pipeline/lrc_format.py
INSTRUMENTAL_RE = re.compile(
	r'\[instrumental:true\]|\[\d{2}:\d{2}\.\d{2}\]\s*(?:\[instrumental\]|\(instrumental\))', re.I
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
	"""The library watcher runs for as long as the server does (ADR 0037), and so does the thread that keeps the
	stored summaries of its albums current (ADR 0067)."""
	library.start()
	stop = threading.Event()
	threading.Thread(target=prefill_summaries, args=(stop,), daemon=True, name='summaries').start()
	yield
	stop.set()
	library.stop()


app = FastAPI(lifespan=lifespan)
job = {
	'path': None,
	'state': 'idle',
	'lines': [],
	'rc': None,
	'queue': [],
	'stop': False,
	'ctx': None,  # the Context of the running job (Stop ends its tools)
	'step': '',  # the pipeline step running now, as the UI names it ('' between steps)
}  # lines accumulate across runs
lock = threading.Lock()


def safe(p: str) -> Path:
	"""Resolve p and require it under the staging or the library folder (trust boundary for every endpoint)."""
	path = Path(p).resolve()
	if not any(path == base or base in path.parents for base in (ROOT, INGEST)):
		raise HTTPException(400, 'path outside the staging and library folders')
	return path


def folder_of(album: Path) -> str:
	"""Where an album is now: its path below the staging or the library folder (the inspector's "Current folder")."""
	base = INGEST if in_library(album) else ROOT
	try:
		return album.relative_to(base).as_posix()
	except ValueError:
		return album.name


def in_library(path: Path) -> bool:
	"""True for a path in the library folder (and not also in the staging folder)."""
	return (path == INGEST or INGEST in path.parents) and not (path == ROOT or ROOT in path.parents)


def lyric_kind(t: Tags) -> str:
	"""instr (instrumental marker, or no lyrics with language zxx), lrc (synced), txt (plain) or none."""
	ly = tag(t, 'LYRICS')
	if not ly.strip():
		return 'instr' if tag(t, 'LYRICS_LANGUAGE') == 'zxx' else 'none'
	if INSTRUMENTAL_RE.search(ly):  # before lrc: the canonical block contains [00:00.00]
		return 'instr'
	return 'lrc' if SYNCED_RE.search(ly) else 'txt'


def track_dr_mean(tags: list[Tags]) -> str:
	"""Album DR fallback: mean of the per-track DYNAMIC_RANGE tags."""
	vals = [int(v) for t in tags if (v := tag(t, 'DYNAMIC_RANGE')).isdigit() and int(v) > 0]
	return str(round(sum(vals) / len(vals))).zfill(2) if vals else ''


def track_files(
	album: Path,
	files: list[Path],
	tags: list[Tags],
	lengths: list[float],
	channels: list[int],
	has_discogs: bool,
) -> list[dict]:
	"""Per-track rows; checks[i] answers pipeline step i (same order as steps in summarize)."""
	out = []
	for f, t, length, ch in zip(files, tags, lengths, channels, strict=False):
		kind = lyric_kind(t)
		tags_ok = (
			has_discogs
			and all(tag(t, *k) for k in REQUIRED_TAGS)
			and bool(tag(t, 'DATE', 'YEAR'))
			and bool(tag(t, 'VERSION'))
		)
		out.append(
			{
				'name': f.name,
				'length': round(length),
				'channels': ch,
				'file': str(f.relative_to(album)),
				'disc': tag(t, 'DISCNUMBER'),
				'track': tag(t, 'TRACKNUMBER'),
				'title': tag(t, 'TITLE') or f.stem,
				'dr': tag(t, 'DYNAMIC_RANGE'),
				'lyrics': kind,
				'checks': [
					bool(tag(t, 'DYNAMIC_RANGE')),
					bool(tag(t, 'REPLAYGAIN_ALBUM_GAIN')),
					bool(tag(t, 'ACOUSTID_FINGERPRINT', 'ACOUSTID FINGERPRINT')),
					tags_ok,
					kind != 'none',
					f.name == file_name(t, f.suffix.lower()),
				],
			}
		)
	return out


COVER_FILES = ('cover.jpg', 'folder.jpg', 'cover.png', 'folder.png')


def cover_info(a: Audio, album: Path) -> dict | None:
	"""Size of the cover that /api/cover serves (embedded front cover first, else a folder image)."""
	pics = a.pictures
	pic = next((p for p in pics if p.type == 3), pics[0] if pics else None)
	if pic:
		w, h = pic.width, pic.height
		if not (w and h):  # some taggers leave the dimensions unset
			try:
				with Image.open(io.BytesIO(pic.data)) as im:
					w, h = im.width, im.height
			except OSError, UnidentifiedImageError:
				pass
		return {'w': w, 'h': h, 'bytes': len(pic.data), 'embedded': True}
	for name in COVER_FILES:
		img = album / name
		if img.is_file():
			try:
				with Image.open(img) as im:
					return {
						'w': im.width,
						'h': im.height,
						'bytes': img.stat().st_size,
						'embedded': False,
					}
			except OSError, UnidentifiedImageError:
				return None
	return None


MISSING_LABEL = {
	'Dynamic range': 'No DR',
	'ReplayGain': 'No ReplayGain',
	'Fingerprints': 'No fingerprints',
	'Tags and cover': 'Tags incomplete',
	'Lyrics': 'No lyrics',
	'Filenames': 'Names differ',
}


def missing_steps(files: list[dict], steps: list[dict]) -> list[dict]:
	"""What exactly is open: per open step the tracks that fail it, with a short label for badges (ADR 0039)."""
	out = []
	for i, step in enumerate(steps):
		bad = [f for f in files if not f['checks'][i]]
		if bad:
			out.append(
				{
					'step': step['name'],
					'label': MISSING_LABEL.get(step['name'], step['name']),
					'optional': step['name'] in OPTIONAL_STEPS,
					'count': len(bad),
					'of': len(files),
					'tracks': [f['title'] or f['file'] for f in bad[:12]],
				}
			)
	return out


EXPORT_COLUMNS = (
	'Album Artist',
	'Album',
	'Version',
	'DR',
	'Format',
	'Edition',
	'Original Title',
	'Original Date',
	'Release Date',
	'Catalog Number',
	'Discogs Release ID',
	'MusicBrainz Album ID',
	'Subtitle',
)


def album_export(t: Tags) -> dict[str, str]:
	"""The album's row of the library export (ADR 0077): the tags of its first file under the column names of the
	discogs repository's albums.csv, which this replaces. Album is the title override, else the master title, else the
	original title, else ALBUM without a trailing `[...]`."""
	album = (
		tag(t, 'ALBUM_TITLE_OVERRIDE', 'ALBUM_MASTER_TITLE', 'ORIGINAL_TITLE')
		or tag(t, 'ALBUM').split('[')[0].strip()
	)
	return {
		'Album Artist': tag(t, 'ALBUMARTIST'),
		'Album': album,
		'Version': tag(t, 'VERSION', 'SUBTITLE'),
		'DR': tag(t, 'ALBUM_DR'),
		'Format': tag(t, 'ALBUM_FORMAT'),
		'Edition': tag(t, 'ALBUM_EDITION'),
		'Original Title': tag(t, 'ORIGINAL_TITLE'),
		'Original Date': tag(t, 'ORIGINALDATE'),
		'Release Date': tag(t, 'RELEASEDATE'),
		'Catalog Number': tag(t, *CATALOG_KEYS),
		'Discogs Release ID': tag(t, 'DISCOGS_RELEASE_ID'),
		'MusicBrainz Album ID': tag(t, 'MUSICBRAINZ_ALBUMID'),
		'Subtitle': tag(t, 'SUBTITLE'),
	}


def summarize(album: Path) -> dict:
	files = flacs(album)
	if not files:
		raise HTTPException(404, 'no flac files')
	audio = [open_audio(f) for f in files]
	tags = [a.tags or {} for a in audio]
	t0 = tags[0]
	did = tag(t0, 'DISCOGS_RELEASE_ID')
	mid = tag(t0, 'MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID')
	out = {
		'path': str(album),
		'name': album.name,
		'folder': folder_of(album),
		'artist': tag(t0, 'ALBUMARTIST', 'ARTIST'),
		'artist_is_albumartist': bool(tag(t0, 'ALBUMARTIST')),
		'new_title': bliss_album(t0),
		'album': tag(t0, 'ALBUM'),
		'cover': cover_info(audio[0], album),
		'artist_override': tag(t0, 'ALBUM_ARTIST_OVERRIDE'),
		'title_override': tag(t0, 'ALBUM_TITLE_OVERRIDE'),
		'year': tag(t0, 'DATE', 'YEAR')[:4],
		'catalog': tag(t0, *CATALOG_KEYS[:1]),
		'country': tag(
			t0, 'DISCOGS_ALBUM_RELEASECOUNTRY', 'COUNTRY', 'MUSICBRAINZ_ALBUM_RELEASECOUNTRY'
		),
		'media': tag(t0, 'ALBUM_FORMAT'),
		'version': tag(t0, 'VERSION'),
		'discogs': did,
		'mbid': mid,
		'tracks': len(files),
		'edition': ' · '.join(x for x in (tag(t0, 'VERSION'), tag(t0, 'CATALOGNUMBER')) if x),
		'mtime': max(f.stat().st_mtime for f in files),
		'export': album_export(t0),
	}
	n = len(tags)

	def have(*k: str) -> bool:
		return sum(1 for t in tags if tag(t, *k)) == n

	kinds = [lyric_kind(t) for t in tags]
	syn, pla, ins, mis = (kinds.count(k) for k in ('lrc', 'txt', 'instr', 'none'))
	req = all(have(*k) for k in REQUIRED_TAGS) and have('DATE', 'YEAR') and have('VERSION')
	cov = out['cover']
	small_cover = MIN_COVER > 0 and (not cov or cov['w'] < MIN_COVER or cov['h'] < MIN_COVER)
	steps = [
		('Dynamic range', have('DYNAMIC_RANGE')),
		('ReplayGain', have('REPLAYGAIN_ALBUM_GAIN')),
		('Fingerprints', have('ACOUSTID_FINGERPRINT', 'ACOUSTID FINGERPRINT')),
		('Tags and cover', bool(did) and req),
		('Lyrics', mis == 0),
		(
			'Filenames',
			all(
				f.name == file_name(t, f.suffix.lower()) for f, t in zip(files, tags, strict=False)
			),
		),  # None (not ready) never equals a name
	]
	out.update(
		dr=tag(t0, 'ALBUM_DR') or track_dr_mean(tags),
		files=track_files(
			album,
			files,
			tags,
			[a.info.length for a in audio],
			[a.info.channels for a in audio],
			bool(did),
		),
		lyrics={'synced': syn, 'plain': pla, 'instrumental': ins, 'missing': mis},
		# partial = done but worth a look (yellow, still counts as done): some lyrics are plain text only, or the cover is small
		steps=[
			{
				'name': a,
				'done': b,
				'partial': b
				and ((a == 'Lyrics' and pla > 0) or (a == 'Tags and cover' and small_cover)),
				'note': cover_note(cov) if a == 'Tags and cover' and small_cover else '',
			}
			for a, b in steps
		],
		tags_ok=req,
		steps_done=sum(1 for _, ok in steps if ok),
	)
	out['missing'] = (
		missing_steps(out['files'], out['steps']) if did else []
	)  # a release comes first (ADR 0039)
	out['issues'] = album_issues(out, tags, small_cover)
	out['status'] = status(out)
	return out


def count_text(n: int, total: int, what: str) -> str:
	if n == total:
		return (
			f'No track has {what}.' if total > 1 else f'The track has no {what.split(" ", 1)[-1]}.'
		)
	return f'{n} of {total} tracks {"has" if n == 1 else "have"} no {what.split(" ", 1)[-1]}.'


# Album-level tags the pipeline reads from the FIRST file only (fixtags, bliss): all files must agree.
# (label, keys, action); Discogs-derived tags such as ALBUM are not listed: the next fix run makes them uniform.
ALBUM_LEVEL = (
	('Discogs release ID', ('DISCOGS_RELEASE_ID',), 'search', True),
	('album artist', ('ALBUMARTIST',), 'album', True),
	('catalog number', CATALOG_KEYS, 'album', True),
	('album format', ('ALBUM_FORMAT',), 'album', True),
	('edition', ('ALBUM_EDITION',), 'album', False),
	('MusicBrainz release ID', ('MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID'), 'album', False),
	('album artist override', ('ALBUM_ARTIST_OVERRIDE',), 'album', False),
	('album title override', ('ALBUM_TITLE_OVERRIDE',), 'album', False),
)
MISSING_TEXT = {
	'album artist': 'Set the album artist.',
	'catalog number': "Add a catalog number (enter 'none' if the release has none).",
	'album format': 'Set the album format (for example CD, SACD, Vinyl).',
}


def album_issues(out: dict, tags: list, small_cover: bool) -> list[dict]:
	"""Clearly identifiable problems, one line each: {text, action, level}; recomputed from the tags on every refresh.

	level 'error' (a Discogs release ID problem, listed first) and 'warn' block the album (status needs), 'ingest' blocks only the move to ingest,
	'info' is a notice. action tells the UI which button to offer. Without a Discogs release ID that is the only blocker listed: the assignment
	fills or sets everything else (artist, format, catalog number, titles, numbers), so those lines would only distract.
	"""
	n, issues = len(tags), []

	def missing(*keys: str) -> int:
		return sum(1 for t in tags if not tag(t, *keys))

	if not out['discogs']:
		issues.append(
			{
				'text': 'Add a Discogs release ID before running fixes.',
				'action': 'search',
				'level': 'error',
			}
		)
		return issues  # nothing else is checked before the album has its Discogs data (ADR 0039)
	for label, keys, action, required in ALBUM_LEVEL:
		values = [tag(t, *keys) for t in tags]
		if (
			required and (m := values.count('')) and not (label == 'Discogs release ID' and m == n)
		):  # all empty: the Discogs line above
			text = MISSING_TEXT[label] if m == n else f'{m} of {n} tracks have no {label}.'
			issues.append(
				{
					'text': text,
					'action': action,
					'level': 'error' if label == 'Discogs release ID' else 'warn',
				}
			)
		filled = [v for v in values if v]
		if len(set(filled)) > 1:
			issues.append(
				{
					'text': f'The files disagree on the {label} ({len(set(filled))} different values); it is read from the first file only.',
					'action': action,
					'level': 'error' if label == 'Discogs release ID' else 'warn',
				}
			)
		elif (
			not required and filled and len(filled) < n
		):  # a gap in a required tag is reported above
			issues.append(
				{
					'text': f'The {label} is set on only {len(filled)} of {n} tracks; it is read from the first file only.',
					'action': action,
					'level': 'warn',
				}
			)
	for key, what in (
		('DISCNUMBER', 'a disc number'),
		('TRACKNUMBER', 'a track number'),
		('TITLE', 'a title'),
		('ARTIST', 'an artist'),
	):
		if m := missing(key):
			issues.append({'text': count_text(m, n, what), 'action': 'tracks', 'level': 'warn'})
	numbers = [
		(tag(t, 'DISCNUMBER').split('/')[0], tag(t, 'TRACKNUMBER').split('/')[0])
		for t in tags
		if tag(t, 'DISCNUMBER') and tag(t, 'TRACKNUMBER')
	]
	if dup := sum(1 for v in {x: numbers.count(x) for x in numbers}.values() if v > 1):
		issues.append(
			{
				'text': f'{dup} disc/track number{" is" if dup == 1 else "s are"} used by more than one file.',
				'action': 'tracks',
				'level': 'warn',
			}
		)
	if small_cover:
		issues.append({'text': cover_note(out['cover']), 'action': 'cover', 'level': 'ingest'})
	return sorted(
		issues, key=lambda i: i['level'] != 'error'
	)  # the Discogs lines always come first


OPTIONAL_STEPS = (
	'Lyrics',
)  # shown as missing (info), but they neither keep an album from `fixed` nor from moving


def status(s: dict) -> str:
	"""needs: a blocking issue (no Discogs id, an empty required tag, files that disagree); fixed: all required steps
	done (lyrics are optional, ADR 0050); else ready."""
	if any(i['level'] in ('warn', 'error') for i in s['issues']):
		return 'needs'
	required = [st for st in s['steps'] if st['name'] not in OPTIONAL_STEPS]
	return 'fixed' if all(st['done'] for st in required) else 'ready'


cache: dict[str, tuple[str, dict]] = {}


SUMMARY_VERSION = (
	2  # bump it when summarize() returns something else: stored summaries are then read again
)
summaries = SummaryStore(DATA / 'summaries.db')


def library_signatures() -> dict[str, tuple[tuple[str, int, int], ...]] | None:
	return library.album_signatures(INGEST)


def album_signature(album: Path, fresh: bool = False, sigs: dict | None = None) -> str:
	"""What an album's summary depends on, as one string: its files (path inside the album), mtimes and sizes. For an
	album of the library it comes from the watcher's index, so no file is touched; with `fresh`, or for any other
	album, the files are stat'ed (ADR 0067). Both give the same string for the same state. A caller that handles many
	albums passes `sigs` (the index's answer, read once): reading it for every album is slow."""
	if sigs is None and not fresh and in_library(album):
		sigs = library_signatures()
	if not fresh and in_library(album) and sigs is not None:
		rel = '' if album == INGEST else album.relative_to(INGEST).as_posix()
		if rel in sigs:
			return json.dumps([SUMMARY_VERSION, sigs[rel]])
	files = []
	for f in flacs(album):
		st = f.stat()
		files.append((f.relative_to(album).as_posix(), st.st_mtime_ns, st.st_size))
	return json.dumps([SUMMARY_VERSION, sorted(files)])


def get_summary(album: Path, fresh: bool = False, sigs: dict | None = None) -> dict:
	"""summarize(), remembered in memory and in SQLite by the album's signature: reading the tags of a whole library
	takes minutes on a network volume (ADR 0067)."""
	key, sig = str(album), album_signature(album, fresh, sigs)
	if (hit := cache.get(key)) and hit[0] == sig:
		return hit[1]
	if (row := summaries.get(key)) and row[0] == sig:
		cache[key] = (sig, row[1])
		return row[1]
	s = summarize(album)
	cache[key] = (sig, s)
	summaries.put(key, sig, s)
	return s


def summary_ready(album: Path, sig: str) -> bool:
	key = str(album)
	if (hit := cache.get(key)) and hit[0] == sig:
		return True
	return bool((row := summaries.get(key)) and row[0] == sig)


def prefill_once(stop: threading.Event | None = None) -> int:
	"""One pass: read the albums of the library whose stored summary is missing or out of date, two at a time (the
	share is slow, and the watcher uses it too). Returns how many were read; 0 while the index is not ready."""
	sigs = library_signatures()
	if sigs is None:
		return 0
	albums_ = [INGEST / rel if rel else INGEST for rel in sigs]
	todo = [a for a in albums_ if not summary_ready(a, album_signature(a, sigs=sigs))]
	summaries.keep_only({str(a) for a in albums_})
	if todo:
		log.info('summaries: reading %d of %d albums', len(todo), len(albums_))
		started = time.time()
		with ThreadPoolExecutor(2) as ex:
			list(ex.map(lambda a: bool(stop and stop.is_set()) or safe_summary(a, sigs=sigs), todo))
		log.info('summaries: %d albums read in %.0f s', len(todo), time.time() - started)
	return len(todo)


def prefill_summaries(stop: threading.Event, interval: float = 60.0) -> None:
	"""Keep the stored summaries of the library current in the background, so that switching to the library never
	waits for the share (ADR 0067). Runs until `stop` is set."""
	wait = 5.0  # the first pass soon after start, once the watcher has listed the library
	while not stop.wait(wait):
		try:
			prefill_once(stop)
		except Exception:  # the thread must survive anything
			log.exception('summaries: a pass failed')
		wait = interval


def fresh_summary(album: Path) -> dict:
	"""After a write: drop the cached summary first. A write that keeps the size (it fits the FLAC padding) on a network
	volume with coarse or cached timestamps would otherwise match the old signature and show the old state."""
	cache.pop(str(album), None)
	summaries.delete(str(album))
	if in_library(album):
		library.refresh(
			album
		)  # the watcher lists it again: a changed tag may change the album's place
	return get_summary(album)


@app.get('/api/dirs')
def dirs(path: str = '') -> dict:
	p = safe(path) if path else ROOT
	subs = sorted(d.name for d in p.iterdir() if d.is_dir() and not d.name.startswith('.'))
	return {'path': str(p), 'root': str(ROOT), 'dirs': subs}


def unreadable_summary(a: Path, error: str) -> dict:
	"""The summary of an album that could not be read, with every field the UI uses, so one bad file does not break
	the board: a red card whose inspector says what failed."""
	return {
		'path': str(a),
		'name': a.name,
		'folder': folder_of(a),
		'artist': '',
		'artist_is_albumartist': False,
		'artist_override': '',
		'title_override': '',
		'album': '',
		'new_title': '',
		'year': '',
		'catalog': '',
		'country': '',
		'media': '',
		'version': '',
		'edition': '',
		'discogs': '',
		'mbid': '',
		'dr': '',
		'mtime': 0,
		'tracks': 0,
		'cover': None,
		'lyrics': {'synced': 0, 'plain': 0, 'instrumental': 0, 'missing': 0},
		'files': [],
		'steps': [{'name': n, 'done': False, 'partial': False, 'note': ''} for n in MISSING_LABEL],
		'steps_done': 0,
		'issues': [{'text': f'This album cannot be read: {error}', 'action': '', 'level': 'error'}],
		'missing': [],
		'status': 'needs',
		'error': error,
	}


def safe_summary(a: Path, fresh: bool = False, sigs: dict | None = None) -> dict:
	try:
		return get_summary(a, fresh, sigs)
	except Exception as e:  # one unreadable album must not break the list
		return unreadable_summary(a, str(e) or type(e).__name__)


@app.get('/api/albums')
def albums(path: str = '', fresh: bool = False) -> dict:
	"""The albums below a folder with their summaries. For the library the album list and the check for changes
	come from the watcher's index, not from the share; `fresh` reads the share (the refresh button, ADR 0067)."""
	base = safe(path) if path else ROOT
	sigs = library_signatures() if base == INGEST and not fresh else None
	dirs = (
		[INGEST / rel if rel else INGEST for rel in sorted(sigs)]
		if sigs is not None
		else album_dirs(base)
	)
	with ThreadPoolExecutor(8) as ex:
		res = list(ex.map(lambda a: safe_summary(a, fresh, sigs), dirs))
	res.sort(key=lambda s: s['mtime'], reverse=True)
	return {'base': str(base), 'albums': res}


@app.get('/api/album')
def album(path: str) -> dict:
	p = safe(path)
	if not p.is_dir():
		raise HTTPException(
			404, 'no flac files'
		)  # the folder is gone, for example moved by the watcher
	return get_summary(p)


def make_picture(data: bytes) -> Cover:
	"""Front-cover Picture from image bytes: JPEG and PNG are kept, anything else becomes JPEG, and an image larger
	than the maximum cover size (a setting, 1500 px) is scaled down (400 if unreadable)."""
	try:
		with Image.open(io.BytesIO(data)) as im:
			fmt, w, h, mode = im.format, im.width, im.height, im.mode
			if fmt not in ('JPEG', 'PNG'):  # FLAC players expect JPEG or PNG
				buf = io.BytesIO()
				im.convert('RGB').save(buf, 'JPEG', quality=95)
				data, fmt, mode = buf.getvalue(), 'JPEG', 'RGB'
	except (OSError, UnidentifiedImageError) as e:
		raise HTTPException(400, 'not a readable image') from e
	pic = new_cover()
	pic.type, pic.mime, pic.desc, pic.width, pic.height, pic.data = (
		3,
		f'image/{fmt.lower()}',
		'',
		w,
		h,
		data,
	)
	pic.depth = {'1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32}.get(mode, 24)
	# a large image is scaled at once, to the limit the pipeline uses (ADR 0016), so it never sits in the files oversized
	return covers.resized(pic, MAX_COVER, Path('cover'))


def embed_cover(album: Path, pic: Cover, only_missing: bool = False) -> None:
	"""Replace the front and untyped covers of every file (back cover etc. stay); only_missing: files without any picture."""
	for f in flacs(album):
		a = open_audio(f)
		if only_missing and a.pictures:
			continue
		keep = [p for p in a.pictures if p.type not in (0, 3)]
		a.clear_pictures()
		a.add_picture(pic)
		for p in keep:
			a.add_picture(p)
		a.save()


@app.put('/api/cover')
async def set_cover(path: str, request: Request) -> dict:
	"""Replace the embedded front cover of every file with the uploaded image (raw request body)."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(path)
	embed_cover(album, make_picture(await request.body()))
	log.info('cover replaced: %s', album.name)
	return fresh_summary(album)


@app.delete('/api/cover')
def delete_cover(path: str) -> dict:
	"""Remove the front and untyped covers from every file (other picture types stay) and the folder images (ADR 0024)."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(path)
	for f in flacs(album):
		a = open_audio(f)
		keep = [p for p in a.pictures if p.type not in (0, 3)]
		if len(keep) != len(a.pictures):
			a.clear_pictures()
			for p in keep:
				a.add_picture(p)
			a.save()
	for name in COVER_FILES:
		(album / name).unlink(missing_ok=True)
	log.info('cover removed: %s', album.name)
	return fresh_summary(album)


@app.get('/api/cover')
def cover(path: str) -> Response:
	album = safe(path)
	for f in flacs(album)[:1]:
		pics = open_audio(f).pictures
		pic = next((p for p in pics if p.type == 3), pics[0] if pics else None)
		if pic:
			return Response(pic.data, media_type=pic.mime or 'image/jpeg')
	for name in COVER_FILES:
		img = album / name
		if img.is_file():
			return FileResponse(img)
	return Response(status_code=204)  # no art: 204 keeps the browser console free of 404s


# Pipeline step -> the step of the UI's pipeline row it works on (dot_clean has none).
UI_STEP = {
	'Dynamic range': 'Dynamic range',
	'ReplayGain': 'ReplayGain',
	'Fingerprints': 'Fingerprints',
	'Discogs tags': 'Tags and cover',
	'Lyrics': 'Lyrics',
}


class JobLog(logging.Handler):
	"""Copies what the pipeline logs into the job log that the UI polls (ADR 0008)."""

	def emit(self, record: logging.LogRecord) -> None:
		job['lines'].append(self.format(record))


# The pipeline step(s) behind a step of the UI's pipeline row, for running one step alone (ADR 0051); Filenames has none.
PIPELINE_OF = {
	'Dynamic range': ['Dynamic range'],
	'ReplayGain': ['ReplayGain'],
	'Fingerprints': ['Fingerprints'],
	'Tags and cover': ['Discogs tags'],
	'Lyrics': ['Lyrics'],
	'Filenames': [],
}


# Steps that measure the audio and need no tags: they run on an album that still needs input (ADR 0051).
AUDIO_STEPS = ('Dynamic range', 'ReplayGain', 'Fingerprints')


def rename_album_files(album: Path) -> list[str]:
	"""Rename the files to the layout's names and log it: one line per album at INFO, each file at DEBUG (ADR 0066)."""
	lines = rename_files(album, file_name)
	done = sum(1 for x in lines if x.startswith('renamed '))
	if done:
		applog.info('renamed %d file(s) in %s', done, album.name)
	for x in lines:
		if x.startswith('skip ') and 'already exists' in x:
			applog.warning('%s: %s', album.name, x)
		else:
			applog.debug('%s: %s', album.name, x)
	return lines


def runner(path: Path, ctx: Context, only: str = '') -> int:
	"""Run the pipeline for one album (or just the UI step `only`), then rename files where that applies.
	Returns 0, or 1 when a step failed (-1 if stopped)."""
	job['path'] = str(path)
	job['lines'].append(f'=== {path.name} ===')
	log.info('job started: %s%s', path.name, f' (step {only})' if only else '')
	try:
		steps = only_steps(*PIPELINE_OF[only]) if only else None
		ok = run_album(
			path, ctx, steps, on_step=lambda name: job.update(step=UI_STEP.get(name, ''))
		)
	except Stopped:
		job['lines'].append('-- stopped by user')
		log.info('job stopped: %s', path.name)
		return -1
	except Exception as e:  # the job thread must survive anything; the message goes to the log pane
		job['lines'].append(f'pipeline failed: {e}')
		log.exception('job crashed: %s', path.name)
		return -1
	if only and only not in ('Filenames', 'Tags and cover'):
		log.info('job finished: %s (%s)', path.name, 'ok' if ok else 'a step failed')
		return 0 if ok else 1
	job['step'] = 'Filenames'
	job['lines'].append('-- rename files')
	job['lines'].extend(rename_album_files(path))
	log.info('job finished: %s (%s)', path.name, 'ok' if ok else 'a step failed')
	return 0 if ok else 1


def worker(paths: list[Path], ctx: Context, only: str = '') -> None:
	"""Process the queue one album at a time; a failure is logged and the queue continues."""
	failed = 0
	handler = JobLog()
	handler.setFormatter(logging.Formatter('%(message)s'))
	pipeline_log = logging.getLogger('pipeline')
	pipeline_log.addHandler(handler)
	pipeline_log.setLevel(logging.INFO)
	try:
		for p in paths:
			if job['stop']:
				break
			job['queue'] = [str(x) for x in paths[paths.index(p) + 1 :]]
			if runner(p, ctx, only) != 0:
				failed += 1
	finally:
		pipeline_log.removeHandler(handler)
		for p in paths:
			if in_library(p):
				library.refresh(p)  # tags were written in place: the watcher lists the album again
		job.update(
			queue=[],
			ctx=None,
			step='',
			rc=1 if failed else 0,
			state='stopped' if job['stop'] else 'failed' if failed else 'done',
		)


@app.post('/api/run')
def run(body: dict) -> dict:
	"""Body: {path} for one album or {paths: [...]} for a queue (the UI starts one album at a time); an optional
	{step: <UI step name>} runs only that step (ADR 0051)."""
	only = str(body.get('step') or '')
	if only and only not in PIPELINE_OF:
		raise HTTPException(400, f'unknown step: {only}')
	raw = body.get('paths') or [body.get('path', '')]
	paths = [safe(p) for p in raw]
	for path in paths:
		if only not in AUDIO_STEPS and get_summary(path)['status'] == 'needs':
			raise HTTPException(
				409, f'{path.name} is not ready: fix the problems listed for it first'
			)
	with lock:  # one heavy task at a time
		if job['state'] == 'running':
			raise HTTPException(409, 'a job is already running')
		ctx = Context(app_config())
		job.update(
			path=str(paths[0]),
			state='running',
			rc=None,
			stop=False,
			ctx=ctx,
			queue=[str(x) for x in paths[1:]],
		)
	threading.Thread(target=worker, args=(paths, ctx, only), daemon=True).start()
	return {'ok': True, 'count': len(paths)}


@app.post('/api/stop')
def stop() -> dict:
	"""Stop the running job: clear the queue and end the tools it started (SIGTERM, SIGKILL after 10 s)."""
	with lock:
		if job['state'] != 'running':
			raise HTTPException(409, 'no job is running')
		job['stop'] = True
		job['queue'] = []
		ctx = job['ctx']
	if ctx:
		ctx.kill()
	return {'ok': True}


def hint(v: str) -> str:
	return '\u2022' * 4 + v[-4:] if v else ''


# ---------- the library: layout template, watcher, status (ADR 0037) ----------
def library_settings() -> LibrarySettings:
	"""The watcher's settings from settings.json, with defaults for anything missing or unusable."""
	cfg = settings.get('library') or {}
	try:
		template = (
			Template.from_dict(cfg['template']) if cfg.get('template') else default_template()
		)
		if validate_template(template)[0]:
			template = default_template()
	except KeyError, TypeError, ValueError, AttributeError:
		template = default_template()

	def number(key: str, default: float) -> float:
		try:
			return float(cfg.get(key, default))
		except TypeError, ValueError:
			return default

	return LibrarySettings(
		apply=bool(cfg.get('apply', True)),
		cooldown=number('cooldown', 60.0),
		interval=number('interval', 120.0),
		sweep_hours=number('sweep_hours', 24.0),
		template=template,
	)


library = Library(lambda: INGEST, DATA / 'library.db', library_settings)


def file_name(t: Tags, suffix: str = '.flac') -> str | None:
	"""The file name the layout gives a file (the bliss name with the default template), or None while a tag it
	needs is empty. The Filenames step and every rename use it, so they agree with the watcher (ADR 0038)."""
	try:
		stem = render_level(
			library_settings().template.filename, {k: tag(t, k) for k in INDEXED_TAGS}
		)
	except MissingTag:
		return None
	return f'{stem}{suffix}' if stem else None


def library_json() -> dict:
	cfg = library_settings()
	return {
		'apply': cfg.apply,
		'cooldown': cfg.cooldown,
		'interval': cfg.interval,
		'sweep_hours': cfg.sweep_hours,
		'template': cfg.template.to_dict(),
		'default_template': default_template().to_dict(),
		'palette': [{'key': k, 'label': v} for k, v in PALETTE.items()],
	}


def parse_library(body: dict) -> dict:
	"""Validate the library part of a settings update; the cleaned dict to store. Raises 400 with what is wrong."""
	old = settings.get('library') or {}
	out: dict = {'apply': bool(body.get('apply', old.get('apply', True)))}
	for key, lo, hi, default in (
		('cooldown', 0, 86400, 60),
		('interval', 10, 86400, 120),
		('sweep_hours', 1, 720, 24),
	):
		try:
			value = float(body.get(key, old.get(key, default)))
		except (TypeError, ValueError) as e:
			raise HTTPException(400, f'{key} must be a number') from e
		if not lo <= value <= hi:
			raise HTTPException(400, f'{key} must be between {lo} and {hi}')
		out[key] = value
	if 'template' in body:
		try:
			template = Template.from_dict(body['template'])
		except (KeyError, TypeError, ValueError, AttributeError) as e:
			raise HTTPException(400, 'the template is malformed') from e
		errors, _ = validate_template(template)
		if errors:
			raise HTTPException(400, 'Template: ' + '; '.join(errors))
		out['template'] = template.to_dict()
	elif old.get('template'):
		out['template'] = old['template']
	return out


@app.get('/api/library')
def get_library() -> dict:
	"""What the watcher is doing and what it found (the top bar's status indicator)."""
	return library.status()


@app.get('/api/library/albums.csv')
def library_albums_csv(path_prefix: str = '') -> Response:
	"""Every album of the library as CSV, from the stored summaries (no file is read; ADR 0077). The columns are those
	of the discogs repository's albums.csv plus `Cover Art` (WIDTHxHEIGHT) and the folder as `_DIRECTORY_PATH` and
	`Directory`. `path_prefix` replaces the library folder at the start of those two paths, for a client that sees the
	same files under another path (the host path of the mount)."""
	out = io.StringIO()
	w = csv.writer(out, lineterminator='\n')
	w.writerow([*EXPORT_COLUMNS, 'Cover Art', '_DIRECTORY_PATH', 'Directory'])
	for s in sorted(albums(str(INGEST))['albums'], key=lambda s: s['path']):
		cov = s['cover'] if s['cover'] and s['cover']['embedded'] else None
		where = (
			str(path_prefix.rstrip('/') + s['path'][len(str(INGEST)) :])
			if path_prefix
			else s['path']
		)
		w.writerow(
			[
				*(s['export'][c] for c in EXPORT_COLUMNS),
				f'{cov["w"]}x{cov["h"]}' if cov else '',
				where,
				where,
			]
		)
	return Response(out.getvalue(), media_type='text/csv; charset=utf-8')


@app.post('/api/library/rescan')
def rescan_library() -> dict:
	"""Re-analyse everything now: a full pass that ignores what the index remembers."""
	library.rescan()
	return {'ok': True}


@app.post('/api/library/preview')
def preview_library(body: dict) -> dict:
	"""What a template would do to one album of the library; nothing is changed."""
	try:
		template = Template.from_dict(body.get('template') or {})
	except (KeyError, TypeError, ValueError, AttributeError) as e:
		raise HTTPException(400, 'the template is malformed') from e
	return library.preview(template, body.get('album'))


def nfs_source(fields: list[str]) -> str:
	"""`host:/export` of an NFS mount; a Docker NFS volume has the host in the `addr=` option only."""
	device = fields[1]
	if device.startswith(':') and (
		m := re.search(r'(?:^|,)addr=([^,]+)', fields[2] if len(fields) > 2 else '')
	):
		return m[1] + device
	return device


def mount_source(path: Path, mountinfo: Path = Path('/proc/self/mountinfo')) -> str:
	"""Where a folder comes from on the host, as the container sees it: the NFS export of the mount
	holding it (`host:/export`) or the bind mount's host path. '' when unknown (not Linux, a layer)."""
	try:
		lines = mountinfo.read_text().splitlines()
	except OSError:
		return ''
	best = ('', '')  # (mount point, source)
	for line in lines:
		left, _, right = line.partition(' - ')
		f, r = left.split(' '), right.split(' ')
		if len(f) < 5 or len(r) < 2:
			continue
		point = f[4].replace('\\040', ' ')
		if (path == Path(point) or Path(point) in path.parents) and len(point) >= len(best[0]):
			root = f[3].replace('\\040', ' ')
			best = (
				point,
				nfs_source(r) if r[0].startswith('nfs') else ('' if root == '/' else root),
			)
	return best[1]


@app.get('/api/settings')
def get_settings() -> dict:
	return {
		'input': str(ROOT),
		'output': str(INGEST),
		'input_source': mount_source(ROOT),
		'output_source': mount_source(INGEST),
		'min_cover': MIN_COVER,
		'max_cover': MAX_COVER,
		'delete_after_move': bool(settings.get('delete_after_move', False)),
		'library': library_json(),
		**{k + '_hint': hint(settings.get(k, '')) for k in KEYS},
	}


@app.post('/api/settings')
def set_settings(body: dict) -> dict:
	"""Blank key keeps the stored key; {clear_<key>: true} removes it. The folders come from the
	environment only (ADR 0045); `input` and `output` in the body are ignored."""
	global MIN_COVER, MAX_COVER
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	try:
		new_min = int(body.get('min_cover', MIN_COVER))
	except (TypeError, ValueError) as e:
		raise HTTPException(400, 'Minimum cover size must be a whole number of pixels') from e
	if not 0 <= new_min <= 20000:
		raise HTTPException(400, 'Minimum cover size must be between 0 and 20000 pixels')
	try:
		new_max = int(body.get('max_cover', MAX_COVER))
	except (TypeError, ValueError) as e:
		raise HTTPException(400, 'Maximum cover size must be a whole number of pixels') from e
	if not 100 <= new_max <= 20000:
		raise HTTPException(400, 'Maximum cover size must be between 100 and 20000 pixels')
	if new_max < new_min:
		raise HTTPException(400, 'Maximum cover size must not be below the minimum cover size')
	new_library = parse_library(body['library']) if isinstance(body.get('library'), dict) else None
	template_changed = new_library is not None and new_library.get('template') != (
		settings.get('library') or {}
	).get('template')
	settings.update(min_cover=new_min, max_cover=new_max)
	if 'delete_after_move' in body:
		settings['delete_after_move'] = bool(body['delete_after_move'])
	settings.pop('input', None)  # ADR 0045: the folders are no longer settings
	settings.pop('output', None)
	if new_library is not None:
		settings['library'] = new_library
	for k in KEYS:
		if body.get('clear_' + k):
			settings.pop(k, None)
		elif str(body.get(k) or '').strip():
			settings[k] = str(body[k]).strip()
	settings.pop('lrclib_api_key', None)  # ADR 0044: the setting is gone, drop a stored value
	DATA.mkdir(parents=True, exist_ok=True)
	SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
	SETTINGS_FILE.chmod(0o600)
	MIN_COVER, MAX_COVER = new_min, new_max
	cache.clear()
	if template_changed:
		library.rescan()  # a new layout applies to everything
	else:
		library.poke()
	log.info('settings saved')
	return get_settings()


@app.get('/api/job')
def get_job(since: int = 0) -> dict:
	return {
		**{k: job[k] for k in ('path', 'state', 'rc', 'queue', 'step')},
		'lines': job['lines'][since:],
		'next': len(job['lines']),
	}


def move_plan(path: Path) -> tuple[dict, list[lib_planner.Move]]:
	"""What "Move to library" would do with an album, and why it cannot (`problems`); nothing is changed."""
	items, problems, files = [], [], []
	if in_library(path):
		return {
			'library': str(INGEST),
			'album_dir': '',
			'files': [],
			'problems': ['this album is already in the library'],
			'can_move': False,
			'stays': '',
		}, []
	s = get_summary(path)
	if job['state'] == 'running':
		problems.append('a job is running')
	if s['status'] != 'fixed':
		problems.append('the album is not fully fixed')
	if any(i['level'] == 'ingest' for i in s['issues']):
		problems.append(
			'the cover is below the minimum size; replace it or lower the minimum in settings'
		)
	for f in flacs(path):
		tags, error = read_tags(f)
		if error:
			problems.append(f'{f.name} cannot be read: {error}')
		else:
			items.append(lib_planner.Item(PurePosixPath(str(f)), tags))
	template = library_settings().template

	def has_disc_dirs(album_dir: tuple[str, ...]) -> bool:
		d = INGEST.joinpath(*album_dir)
		return d.is_dir() and any(is_disc_dir(x.name) for x in d.iterdir() if x.is_dir())

	plan = lib_planner.plan(items, template, has_disc_dirs)
	problems += [f'{p.path.name}: {p.reason}' for p in [*plan.unplaced, *plan.skipped]]
	depth = len(template.folders)
	album_dir = ''
	for m in plan.moves:
		album_dir = album_dir or '/'.join(m.dst.parts[:depth])
		exists = (INGEST / m.dst).exists()
		if exists:
			problems.append(f'{m.dst} already exists in the library; nothing is overwritten')
		files.append({'from': m.src.name, 'name': '/'.join(m.dst.parts[depth:]), 'exists': exists})
	info = {
		'library': str(INGEST),
		'album_dir': album_dir,
		'files': files,
		'problems': problems,
		'can_move': bool(plan.moves) and not problems,
		'stays': (
			'Only the audio files move. When they have moved you are asked whether to delete what is left '
			'of the album folder (images, logs) in the staging folder.'
			if settings.get('delete_after_move')
			else 'Only the audio files move. Other files in the album folder (images, logs) stay in the staging folder.'
		),
	}
	return info, plan.moves


@app.get('/api/move/preview')
def move_preview(path: str) -> dict:
	"""What Move to library will do with this album: the library folder, the album folder and each file name."""
	album = safe(path)
	if album == ROOT or not album.is_dir():
		raise HTTPException(400, 'not an album folder')
	return move_plan(album)[0]


def folder_listing(folder: Path, limit: int = 300) -> dict:
	"""What is in a folder, everything below it included (hidden files too, symlinks not followed): the first `limit`
	files with their sizes and the first `limit` subfolders (empty ones too), the totals, and how many audio files are
	among them."""
	files: list[dict] = []
	folders: list[str] = []
	count = size_total = dirs = audio = 0
	for root, dirnames, names in os.walk(folder, followlinks=False):
		dirs += len(dirnames)
		for d in sorted(dirnames):
			if len(folders) < limit:
				folders.append((Path(root) / d).relative_to(folder).as_posix())
		for name in sorted(names):
			p = Path(root) / name
			try:
				size = p.lstat().st_size
			except OSError:
				size = 0
			count += 1
			size_total += size
			audio += is_audio(name)
			if len(files) < limit:
				files.append({'path': p.relative_to(folder).as_posix(), 'size': size})
	return {
		'path': str(folder),
		'name': folder.name,
		'files': files,
		'folders': folders,
		'count': count,
		'bytes': size_total,
		'dirs': dirs,
		'audio': audio,
		'truncated': count > len(files),
	}


def cleanup_folder(path: str) -> Path:
	"""The folder an album left behind in the staging folder: inside it, never the staging folder itself (ADR 0072)."""
	p = safe(path)
	if p == ROOT or ROOT not in p.parents:
		raise HTTPException(400, 'only a folder inside the staging folder can be deleted')
	if not p.is_dir():
		raise HTTPException(404, 'no such folder')
	return p


@app.get('/api/folder')
def folder(path: str) -> dict:
	"""What a folder of the staging folder still holds: the list the delete dialog shows (ADR 0072)."""
	return folder_listing(cleanup_folder(path))


@app.post('/api/folder/delete')
def folder_delete(body: dict) -> dict:
	"""Delete a folder of the staging folder with everything in it, when Settings allows it and no song is left in it."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	if not settings.get('delete_after_move', False):
		raise HTTPException(409, 'deleting folders after a move is not enabled in Settings')
	p = cleanup_folder(body.get('path', ''))
	listing = folder_listing(p, limit=0)
	if listing['audio']:
		raise HTTPException(
			409, f'{listing["audio"]} song(s) are still in this folder; nothing was deleted'
		)
	shutil.rmtree(p)
	log.info(
		'deleted the folder %s (%d files, %d bytes)', p.name, listing['count'], listing['bytes']
	)
	library.poke()
	return {'deleted': True, 'files': listing['count'], 'bytes': listing['bytes']}


@app.post('/api/move')
def move(body: dict) -> dict:
	"""Place a fixed album in the library: each FLAC goes straight to its path in the layout (ADR 0037)."""
	path = safe(body.get('path', ''))
	if path == ROOT or not path.is_dir():
		raise HTTPException(400, 'not an album folder')
	info, moves = move_plan(path)
	if not info['can_move']:
		raise HTTPException(409, info['problems'][0] if info['problems'] else 'nothing to move')
	with library.exclusive:
		for m in moves:
			dst = INGEST / m.dst
			dst.parent.mkdir(parents=True, exist_ok=True)
			shutil.move(str(m.src), dst)
	library.poke()
	log.info('moved to the library: %s (%d files) -> %s', path.name, len(moves), info['album_dir'])
	return {'moved_to': str(INGEST / info['album_dir'])}


# ---------- track editor: assign album files to a Discogs release ----------
releases: dict[str, dict] = {}  # release id -> parsed tracklist (Discogs allows 60 requests/min)
raw_releases: dict[
	str, dict
] = {}  # release id -> the Discogs release JSON, for the tags written on apply


discogs_api.configure(lambda: settings.get('discogs_api_key', ''))


def discogs(path: str, **params: str | int) -> dict:
	"""A Discogs API call; failures become the HTTP error the UI shows (the client is pipeline/discogs.py)."""
	try:
		return discogs_api.get(path, **params)
	except ApiError as e:
		raise HTTPException(e.status, e.message) from e


def discogs_image(url: str) -> bytes:
	try:
		return discogs_api.image(url)
	except ApiError as e:
		raise HTTPException(e.status, e.message) from e


def artist_names(artists: list[dict]) -> str:
	"""'Name (2)' disambiguation suffixes dropped; Discogs join words ('&', ',') kept."""
	out = ''
	for a in artists:
		out += re.sub(r'\s*\(\d+\)$', '', a.get('name', ''))
		j = a.get('join', '').strip()
		out += (', ' if j == ',' else f' {j} ') if j else ''
	return out.strip()


def seconds(d: str) -> int:
	try:
		m, s = d.split(':')[-2:]
		return int(m) * 60 + int(s)
	except ValueError:
		return 0


WRITER_ROLES = (
	'written-by',
	'written by',
	'composed by',
	'music by',
	'songwriter',
	'lyrics by',
	'words by',
)
COPYRIGHT_TYPES = ('copyright (c)', 'phonographic copyright (p)')


def clean_artist(name: str) -> str:
	return re.sub(r'\s*\(\d+\)$', '', name.strip())


def uniq(xs: Iterable[str | None]) -> list[str]:
	return list(dict.fromkeys(x for x in xs if x))


def by_role(extra: list[dict], *roles: str) -> list[str]:
	"""Names of the credits whose role contains one of the (lower-case) role words."""
	return uniq(
		clean_artist(e.get('name', ''))
		for e in extra
		if any(w in (e.get('role') or '').lower() for w in roles)
	)


def release_format(r: dict) -> str:
	"""The medium of a Discogs release for ALBUM_FORMAT: the first format name, ignoring the wrappers Box Set and All Media."""
	return next(
		(
			f['name'].strip()
			for f in r.get('formats') or []
			if (f.get('name') or '').strip()
			and f['name'].strip().lower() not in ('box set', 'all media')
		),
		'',
	)


def release_tags(r: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
	"""(player tags, DISCOGS_* tags) from a raw Discogs release. Empty values are omitted.

	Player tags are the standard ones the tagger used to import (shown by Roon etc.); they are filled when missing.
	DISCOGS_* tags are Discogs-owned and replaced on every assignment.
	"""
	extra, companies, labels = (
		r.get('extraartists') or [],
		r.get('companies') or [],
		r.get('labels') or [],
	)
	artists = r.get('artists') or []

	def company(*types: str) -> list[str]:
		return uniq(
			clean_artist(c.get('name', ''))
			for c in companies
			if (c.get('entity_type_name') or '').lower() in types
		)

	fmts = ', '.join(
		f['name'] + (f' ({",".join(f["descriptions"])})' if f.get('descriptions') else '')
		for f in r.get('formats') or []
		if f.get('name')
	)
	catnos = uniq(
		(lb.get('catno') or '').strip()
		for lb in labels
		if (lb.get('catno') or '').strip().lower() != 'none'
	)
	barcode = next(
		(
			i['value'].strip()
			for i in r.get('identifiers') or []
			if i.get('type') == 'Barcode' and i.get('value')
		),
		'',
	)
	copyright_ = [f'\u2117 {n}' for n in company('phonographic copyright (p)')] + [
		f'\u00a9 {n}' for n in company('copyright (c)')
	]
	player = {
		'GENRE': uniq(r.get('genres') or []),
		'MOOD': [', '.join(r.get('styles') or [])],  # the tagger put the Discogs styles here
		'LABEL': uniq(clean_artist(lb.get('name', '')) for lb in labels),
		'MEDIA': [fmts],
		'COUNTRY': [r.get('country', '')],
		'BARCODE': [barcode],
		'CATALOG': catnos,
		'COPYRIGHT': [', '.join(copyright_)],
		'PUBLISHER': [', '.join(company('published by'))],
		'PRODUCER': by_role(extra, 'producer'),
		'ENGINEER': by_role(extra, 'engineer'),
		'PERSONNEL': uniq(
			f'{clean_artist(e["name"])} - {e["role"]}'
			for e in extra
			if e.get('name') and e.get('role')
		),
	}
	rid = r['id']
	artist_urls = [f'https://www.discogs.com/artist/{a["id"]}' for a in artists if a.get('id')]
	discogs_tags = {
		'DISCOGS_RELEASE_URL': [r.get('uri', '')],
		'DISCOGS_MASTER_ID': [f'm{r["master_id"]}'] if r.get('master_id') else [],
		'DISCOGS_MASTER_URL': [f'https://www.discogs.com/master/{r["master_id"]}']
		if r.get('master_id')
		else [],
		'DISCOGS_ARTIST_URL': artist_urls,
		'DISCOGS_ALBUMARTIST_URL': artist_urls,
		'DISCOGS_ARTIST_LIST': [', '.join(clean_artist(a.get('name', '')) for a in artists)],
		'DISCOGS_LABEL_URL': [
			f'https://www.discogs.com/label/{lb["id"]}' for lb in labels if lb.get('id')
		],
		'DISCOGS_ARTWORK_URL': [f'https://www.discogs.com/viewimages?release={rid}'],
		'DISCOGS_CATALOG_NUMBER': uniq(
			f'{clean_artist(lb.get("name", ""))}: {lb["catno"]}' for lb in labels if lb.get('catno')
		),
		'DISCOGS_ALBUM_RELEASECOUNTRY': [r.get('country', '')],
		'DISCOGS_RELEASE_NOTES': [(r.get('notes') or '').strip()],
		'DISCOGS_VIDEO_URL': uniq(
			f'{v.get("title", "").strip()}: {v["uri"]}'
			for v in r.get('videos') or []
			if v.get('uri')
		),
	}
	for c in companies:  # Recorded At, Mixed At, Pressed By, ... one tag per role
		role = (c.get('entity_type_name') or '').strip()
		if role and role.lower() not in COPYRIGHT_TYPES:
			key = 'DISCOGS_' + re.sub(r'[^A-Z0-9]+', '_', role.upper()).strip('_')
			discogs_tags.setdefault(key, [])
			name = clean_artist(c.get('name', ''))
			if name and name not in discogs_tags[key]:
				discogs_tags[key].append(name)
	for key in [
		k for k in discogs_tags if k.startswith('DISCOGS_') and k not in DISCOGS_FIXED_KEYS
	]:
		discogs_tags[key] = [', '.join(discogs_tags[key])] if discogs_tags[key] else []
	return (
		{k: [x for x in v if x] for k, v in player.items() if any(v)},
		{k: [x for x in v if x] for k, v in discogs_tags.items() if any(v)},
	)


# DISCOGS_* tags that keep one value per entry instead of one joined value (the rest are per company role)
DISCOGS_FIXED_KEYS = {
	'DISCOGS_RELEASE_URL',
	'DISCOGS_MASTER_ID',
	'DISCOGS_MASTER_URL',
	'DISCOGS_ARTIST_URL',
	'DISCOGS_ALBUMARTIST_URL',
	'DISCOGS_ARTIST_LIST',
	'DISCOGS_LABEL_URL',
	'DISCOGS_ARTWORK_URL',
	'DISCOGS_CATALOG_NUMBER',
	'DISCOGS_ALBUM_RELEASECOUNTRY',
	'DISCOGS_RELEASE_NOTES',
	'DISCOGS_VIDEO_URL',
}


def release_tracks(rid: str) -> dict:
	if rid in releases:
		return releases[rid]
	r = discogs(f'/releases/{rid}')
	album_artist = artist_names(r.get('artists', []))
	tracks, seq, head = [], 0, 0

	def add(t: dict, pos: str, disc: int, track: int, part_of: str = '', duration: int = 0) -> None:
		tracks.append(
			{
				'i': len(tracks),
				'position': pos,
				'disc': disc,
				'track': track,
				'title': t.get('title', ''),
				'part_of': part_of,
				'channels': channels_from_title(t.get('title', '')),
				'duration': duration or seconds(t.get('duration', '')),
				'artist': artist_names(t.get('artists', [])) or album_artist,
				'composers': by_role(t.get('extraartists') or [], *WRITER_ROLES),
				'producers': by_role(t.get('extraartists') or [], 'producer'),
				'engineers': by_role(t.get('extraartists') or [], 'engineer'),
			}
		)

	for t in r.get('tracklist', []):
		if t.get('type_') == 'heading':
			if h := re.match(r'^(?:CD|DVD|Disc|Disk)\s*(\d+)\b', t.get('title', ''), re.I):
				head = int(h[1])  # plain positions 1, 2, ... restart under each 'Disc N' heading
			continue
		parts = t.get('sub_tracks') or [] if t.get('type_') == 'index' else []
		if parts:
			# a medley or a work in parts: the entry itself is one release track (a single file), and its parts
			# (CD3-6.1, CD3-6.2, ... or plain 6, 7, ...) are tracks of their own for files split by part (ADR 0060)
			pos = re.sub(r'\.\d+$', '', parts[0].get('position', ''))
		elif t.get('type_') == 'track':
			pos = t.get('position', '')
		else:
			continue
		m = re.match(r'^(?:CD|DVD)?(\d+)[-.](\d+)$', pos, re.I)
		if not m and head and pos.isdigit():
			m = (None, head, pos)
		seq += 1
		disc, number = (int(m[1]) if m else 1), (int(m[2]) if m else seq)
		add(t, pos, disc, number, duration=sum(seconds(p.get('duration', '')) for p in parts))
		for part in parts:
			add(part, part.get('position', ''), disc, number, part_of=t.get('title', ''))
	# Discogs' own 'none' counts: the tag must not be empty
	catno = next((c for lb in r.get('labels', []) if (c := (lb.get('catno') or '').strip())), '')
	images = r.get('images') or []
	image = next(
		(i for i in images if i.get('type') == 'primary'), images[0] if images else {}
	).get('uri', '')
	out = {
		'id': str(r['id']),
		'title': r.get('title', ''),
		'artist': album_artist,
		'year': r.get('year', ''),
		'catno': catno,
		'master_id': r.get('master_id') or 0,
		'image': image,
		'tracks': tracks,
	}
	releases[rid] = out
	raw_releases[rid] = r
	return out


def release_album_title(rel: dict) -> str:
	"""Album title as fixtags derives it: master title, else the release title (fetched once, cached in rel)."""
	if 'album_title' not in rel:
		title = rel['title'].strip()
		if rel['master_id']:
			try:
				title = discogs(f'/masters/{rel["master_id"]}').get('title', title).strip()
			except HTTPException:
				pass
		rel['album_title'] = title
	return rel['album_title']


def brief(r: dict) -> dict:
	"""Search hits and full releases come in different shapes."""
	title = r.get('title', '')
	if r.get('artists'):
		title = f'{artist_names(r["artists"])} - {title}'
	fmt = r.get('format') or [f['name'] for f in r.get('formats', [])]
	label = r.get('label') or [lb['name'] for lb in r.get('labels', [])]
	return {
		'id': str(r['id']),
		'title': title,
		'year': r.get('year', ''),
		'country': r.get('country', ''),
		'format': ', '.join(fmt[:3]),
		'label': ', '.join(label[:2]),
		'catno': r.get('catno') or (r.get('labels') or [{}])[0].get('catno', ''),
		'thumb': r.get('thumb', ''),
	}


@app.get('/api/discogs/search')
def discogs_search(q: str, path: str = '') -> list[dict]:
	"""Release search; with an album `path` whose MusicBrainz release links Discogs releases, those come first,
	marked `match: 'MusicBrainz'` (ADR 0052)."""
	q = q.strip()
	if q.isdigit():
		rows = [brief(discogs(f'/releases/{q}'))]
	else:
		rows = [
			brief(r)
			for r in discogs('/database/search', type='release', q=q, per_page=20).get(
				'results', []
			)
		]
	linked: list[str] = []
	if path and (mbid := get_summary(safe(path))['mbid']):
		try:
			linked = mb_release(mbid)['discogs_ids']
		except HTTPException:
			pass  # MusicBrainz unreachable: the plain results are still right
	for r in rows:
		r['match'] = 'MusicBrainz' if r['id'] in linked else ''
	return sorted(rows, key=lambda r: not r['match'])  # stable: the rest keep Discogs' order


@app.get('/api/discogs/tracks')
def discogs_tracks(id: str) -> dict:
	"""Track count of a release (cached with the parsed tracklist)."""
	return {'count': len(release_tracks(id.strip())['tracks'])}


def norm_title(s: str) -> str:
	return re.sub(
		r'[^a-z0-9]+',
		' ',
		unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode(),
	).strip()


def album_files(album: Path) -> list[dict]:
	out = []
	for f in flacs(album):
		a = open_audio(f)
		t = a.tags or {}
		out.append(
			{
				'file': str(f.relative_to(album)),
				'title': tag(t, 'TITLE') or f.stem,
				'duration': round(a.info.length),
				'channels': a.info.channels,
				'disc': int(m[0]) if (m := re.match(r'\d+', tag(t, 'DISCNUMBER') or '1')) else 1,
				'track': int(m[0]) if (m := re.match(r'\d+', tag(t, 'TRACKNUMBER'))) else 0,
			}
		)
	return sorted(out, key=lambda x: (x['disc'], x['track'], x['file']))


@app.post('/api/tracks/propose')
def tracks_propose(body: dict) -> dict:
	"""Release tracklist, album files and a suggested file -> release track assignment."""
	album = safe(body.get('path', ''))
	rel = release_tracks(str(body.get('release_id', '')).strip())
	files = album_files(album)
	pairs = []
	for f in files:
		for t in rel['tracks']:
			s = SequenceMatcher(None, norm_title(f['title']), norm_title(t['title'])).ratio() * 0.6
			if t['duration']:
				s += max(0.0, 1 - abs(f['duration'] - t['duration']) / 8) * 0.25
			if f['track'] and (f['disc'], f['track']) == (t['disc'], t['track']):
				s += 0.15
			pairs.append((s, f['file'], t['i']))
	assign: dict[str, int | None] = {f['file']: None for f in files}
	conf: dict[str, float] = {}
	used: set[int] = set()
	is_part = {t['i']: bool(t['part_of']) for t in rel['tracks']}
	# whole tracks first; the parts of a medley only take the files left over, and only on a clear title match (ADR 0060)
	for part_pass in (False, True):
		for s, fn, i in sorted(pairs, reverse=True):
			if is_part[i] != part_pass or assign[fn] is not None or i in used:
				continue
			if s >= (0.45 if part_pass else 0.35):
				assign[fn], conf[fn] = i, round(s, 2)
				used.add(i)
	return {
		'release': rel,
		'files': [{**f, 'rel': assign[f['file']], 'conf': conf.get(f['file'], 0)} for f in files],
	}


@app.post('/api/tracks/apply')
def tracks_apply(body: dict) -> dict:
	"""Write release id and per-track tags for the assigned files, refresh the Discogs-owned tags, then rename the files.

	Tracks are renumbered 1..n per disc in release order, so a subset of the release gets no gaps.
	Files without an assignment are left untouched.
	"""
	album = safe(body.get('path', ''))
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	rel = release_tracks(str(body.get('release_id', '')).strip())
	asg = [a for a in body.get('assignments', []) if a.get('rel') is not None]
	chosen = {a['file']: a['rel'] for a in asg}
	if len({*chosen.values()}) != len(chosen):
		raise HTTPException(400, 'a release track is assigned twice')
	# default numbering: 1..n per disc in release order; the UI may override disc and track per file
	picked = sorted(chosen.items(), key=lambda kv: kv[1])
	discs = sorted({rel['tracks'][i]['disc'] for _, i in picked})
	seen: dict[int, int] = {}
	final: dict[str, tuple[int, int]] = {}
	for fn, i in picked:
		d = rel['tracks'][i]['disc']
		seen[d] = seen.get(d, 0) + 1
		final[fn] = (discs.index(d) + 1, seen[d])
	for a in asg:
		try:
			final[a['file']] = (
				int(a.get('disc') or final[a['file']][0]),
				int(a.get('track') or final[a['file']][1]),
			)
		except (TypeError, ValueError) as e:
			raise HTTPException(400, 'disc and track must be numbers') from e
	per_disc: dict[int, int] = {}
	for d, _ in final.values():
		per_disc[d] = per_disc.get(d, 0) + 1
	log = []
	filled: dict[str, int] = {}

	prev_vals: dict[
		str, list[str]
	] = {}  # what the file's previous Discogs release would have filled
	prev_cache: dict[str, dict[str, list[str]]] = {}

	def release_level(rid: str) -> dict[str, list[str]]:
		"""The release-level tags an assignment fills from release `rid` ({} when it cannot be read)."""
		if rid not in prev_cache:
			found: dict[str, list[str]] = {}
			try:
				r = release_tracks(rid)
				if raw := raw_releases.get(rid):
					found = {
						'CATALOGNUMBER': [r['catno']],
						'ALBUM_FORMAT': [release_format(raw)],
						'ALBUMARTIST': [r['artist']],
						'ALBUM': [release_album_title(r)],
						**{
							k: v
							for k, v in release_tags(raw)[0].items()
							if k not in ('PRODUCER', 'ENGINEER')
						},
					}
			except HTTPException:
				pass
			prev_cache[rid] = {k: v for k, v in found.items() if v and v != ['']}
		return prev_cache[rid]

	def fill(a: Audio, key: str, value: str | list[str], *alts: str) -> None:
		# Tags the tagger used to import from Discogs (the pipeline reads some as user input): filled when empty,
		# never overwritten (discogs ADR 0002 section 1 and 2), except a value the file's previous Discogs
		# release itself would have filled: that follows the release (ADR 0048).
		values = [value] if isinstance(value, str) else value
		stale = key in prev_vals and list(a.tags.get(key) or []) == prev_vals[key]
		if values and (not tag(a.tags, key, *alts) or stale):
			a[key] = values
			filled[key] = filled.get(key, 0) + 1

	player, discogs_tags = release_tags(raw_releases[rel['id']])
	writers = by_role(raw_releases[rel['id']].get('extraartists') or [], *WRITER_ROLES)

	cover = None
	if not open_audio(flacs(album)[0]).pictures and rel['image']:
		try:
			cover = make_picture(discogs_image(rel['image']))
		except HTTPException as e:
			log.append(f'cover not fetched: {e.detail}')
	for fn, i in picked:
		t = rel['tracks'][i]
		d, n = final[fn]
		a = open_audio(album / fn)
		if a.tags is None:
			a.add_tags()
		before = tag(a.tags, 'DISCOGS_RELEASE_ID')
		prev_vals.clear()
		if before and before != rel['id']:
			prev_vals.update(release_level(before))
		a['DISCOGS_RELEASE_ID'] = [rel['id']]
		if rel['catno'].lower() != 'none' and tag(a.tags, *CATALOG_KEYS).lower() == 'none':
			for k in CATALOG_KEYS:  # Discogs' own 'none' is a placeholder, a real catalogue number replaces it (ADR 0047)
				if k in a:
					del a[k]
		fill(a, 'CATALOGNUMBER', rel['catno'], *CATALOG_KEYS[1:])
		fill(a, 'ALBUM_FORMAT', release_format(raw_releases[rel['id']]))
		fill(a, 'ARTIST', t['artist'])
		if not tag(a.tags, 'ALBUM_ARTIST_OVERRIDE'):
			fill(a, 'ALBUMARTIST', rel['artist'])
		if not tag(a.tags, 'ALBUM_TITLE_OVERRIDE'):
			fill(a, 'ALBUM', release_album_title(rel))
		for key, values in player.items():
			if key not in ('PRODUCER', 'ENGINEER'):
				fill(a, key, values)
		fill(a, 'COMPOSER', t['composers'] or writers)  # track credits win over release credits
		fill(a, 'PRODUCER', t['producers'] or player.get('PRODUCER', []))
		fill(a, 'ENGINEER', t['engineers'] or player.get('ENGINEER', []))
		for key in [
			k
			for k in a.tags.keys()
			if k.upper().startswith('DISCOGS_') and k.upper() != 'DISCOGS_RELEASE_ID'
		]:
			del a.tags[key]  # Discogs-owned: replaced by the data of this release
		for key, values in discogs_tags.items():
			a[key] = values
		a['DISCOGS_RELEASE_ORDINAL_POSITION'] = [str(t['i'])]
		if t['position']:
			a['TRACK_NUMBER_TEXT'] = [t['position']]
		a['TITLE'] = [t['title']]
		a['TRACKNUMBER'] = [str(n)]
		a['DISCNUMBER'] = [str(d)]
		a['TRACKTOTAL'] = a['TOTALTRACKS'] = [str(per_disc[d])]
		a['DISCTOTAL'] = a['TOTALDISCS'] = [str(len(per_disc))]
		a.save()
		log.append(f'{fn}: {d}-{n:02d} {t["title"]}')
	if cover:
		embed_cover(album, cover, only_missing=True)
		filled['cover'] = 1
	for f in flacs(album):  # a skipped file keeps its own release; say so, the album then has two
		other = tag(open_audio(f).tags, 'DISCOGS_RELEASE_ID')
		if f.name not in chosen and other and other != rel['id']:
			log.append(f'{f.name} was skipped and keeps Discogs release {other}, not {rel["id"]}')
	log.append(f'Discogs-owned tags written: {len(discogs_tags) + 1} per file')
	if filled:
		log.append(
			'filled from Discogs: '
			+ ', '.join(f'{k} x{v}' if v > 1 else k for k, v in filled.items())
		)
	# The Discogs-owned tags of the new release (year, album title, version, label ...) at once, as a run would write
	# them, so the card and the inspector do not keep the previous release's data (ADR 0013).
	log.append(refresh_discogs_tags(album))
	log += rename_album_files(album)
	logging.getLogger('app').info(
		'assigned Discogs release %s to %s (%d files)', rel['id'], album.name, len(picked)
	)
	return {'log': log, 'album': fresh_summary(album)}


def refresh_discogs_tags(album: Path) -> str:
	"""Write the Discogs-owned tags (year, album title, VERSION ...) now, as a run would; the log line says how it went."""
	try:
		fixed = fix_album(album, app_config())
	except ApiError as e:
		return f'Discogs tags not refreshed: {e.message}; Run fixes does it later'
	if fixed.skipped:
		return f'Discogs tags not refreshed: {fixed.skipped}'
	return f'Discogs tags refreshed: {fixed.album_name} [{fixed.version}] ({fixed.changed} files changed)'


def track_path(album: str, file: str) -> Path:
	f = safe(str(safe(album) / file))
	if not is_audio(f.name) or not f.is_file():
		raise HTTPException(404, 'no such track')
	return f


@app.get('/api/audio')
def audio(path: str, file: str) -> FileResponse:
	f = track_path(path, file)
	return FileResponse(f, media_type='audio/mpeg' if f.suffix.lower() == '.mp3' else 'audio/flac')


@app.get('/api/track')
def get_track(path: str, file: str) -> dict:
	f = open_audio(track_path(path, file))
	t = f.tags or {}
	return {
		'title': tag(t, 'TITLE'),
		'artist': tag(t, 'ARTIST'),
		'album': tag(t, 'ALBUM'),
		'lyrics': tag(t, 'LYRICS'),
		'length': round(f.info.length) if f.info else 0,
	}


@app.post('/api/track')
def set_track(body: dict) -> dict:
	"""Edit the lyrics of one file (empty removes the tag). Title and artist are edited in the tag editor's Tracks tab."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	a = open_audio(track_path(body.get('path', ''), body.get('file', '')))
	if a.tags is None:
		a.add_tags()
	lyrics = str(body.get('lyrics', ''))
	if lyrics.strip():
		a['LYRICS'] = [lyrics.strip('\n')]
	elif 'LYRICS' in a.tags:
		del a.tags['LYRICS']
	a.save()
	log.info(
		'lyrics %s: %s / %s',
		f'edited ({len(lyrics.strip())} chars)' if lyrics.strip() else 'removed',
		album.name,
		body['file'],
	)
	return {'log': [f'edited lyrics of {body["file"]}'], 'album': fresh_summary(album)}


# ---- MusicBrainz release search and tags (ADR 0023) ----
# MusicBrainz allows one request a second and wants a User-Agent naming the application; it answers 503 when the
# limit is exceeded. Requests go through one lock, at least 1.1 s apart; a 503 is retried 3 times after 5 s.
mb_releases: dict[str, dict] = {}  # parsed releases, for the life of the process
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
# Written by "Apply" for a chosen release; replaced on every apply. MUSICBRAINZ_ARTISTID and MUSICBRAINZ_ARTIST_URL are
# per file and only touched when the file's title matches exactly one track of the release (see mb_apply).
# The names follow what the tagger (Yate) wrote into the library (MUSICBRAINZ_RELEASE_GROUPID, MUSICBRAINZ_ALBUM_URL, ...); the
# Picard spelling MUSICBRAINZ_RELEASEGROUPID is removed as an alternative so the file has one value, not two.
MB_ALBUM_KEYS = (
	'MUSICBRAINZ_ALBUMID',
	'MUSICBRAINZ ALBUM ID',
	'MUSICBRAINZ_RELEASE_GROUPID',
	'MUSICBRAINZ_RELEASEGROUPID',
	'MUSICBRAINZ_ALBUMARTISTID',
	'MUSICBRAINZ_ALBUM_URL',
	'MUSICBRAINZ_RELEASE_GROUP_URL',
	'MUSICBRAINZ_ALBUMARTIST_URL',
)
MB_TRACK_KEYS = ('MUSICBRAINZ_ARTISTID', 'MUSICBRAINZ_ARTIST_URL')


def musicbrainz(path: str, **params: str | int) -> dict:
	"""A MusicBrainz API call; failures become the HTTP error the UI shows (the client is pipeline/musicbrainz.py)."""
	try:
		return mb_api.get(path, **params)
	except ApiError as e:
		raise HTTPException(e.status, e.message) from e


def mb_names(credit: list[dict] | None) -> str:
	return ''.join(c.get('name', '') + c.get('joinphrase', '') for c in credit or [])


def mb_unique(items: Iterable[str | None]) -> str:
	return ', '.join(dict.fromkeys(x for x in items if x))


def mb_brief(r: dict) -> dict:
	"""Search hits and lookups share these fields (a lookup has no top-level track-count)."""
	media, infos = r.get('media') or [], r.get('label-info') or []
	return {
		'id': r['id'],
		'title': f'{mb_names(r.get("artist-credit"))} - {r.get("title", "")}',
		'year': (r.get('date') or '')[:4],
		'country': r.get('country') or '',
		'format': mb_unique(m.get('format') for m in media),
		'label': mb_unique((i.get('label') or {}).get('name') for i in infos),
		'catno': mb_unique(i.get('catalog-number') for i in infos),
		'barcode': r.get('barcode') or '',
		'tracks': r.get('track-count') or sum(m.get('track-count', 0) for m in media),
		'thumb': f'https://coverartarchive.org/release/{r["id"]}/front-250',
		'match': '',
	}


def mb_discogs_releases(did: str) -> list[str]:
	"""MusicBrainz releases that link this Discogs release (a url relation); none when unknown or on any error."""
	try:
		url = musicbrainz(
			'/url', resource=f'https://www.discogs.com/release/{did}', inc='release-rels'
		)
	except HTTPException:
		return []
	return [r['id'] for rel in url.get('relations', []) if (r := rel.get('release'))][:5]


def lucene(s: str) -> str:
	return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r'\\\1', s)


def mb_hits(query: str, limit: int, match: str, hits: dict) -> None:
	for r in musicbrainz('/release', query=query, limit=limit).get('releases', []):
		hits.setdefault(r['id'], {**mb_brief(r), 'match': match})


@app.get('/api/musicbrainz/search')
def musicbrainz_search(q: str, path: str = '') -> list[dict]:
	"""Release search. With a Discogs ID on the album, releases with the same barcode or catalogue number come first."""
	q = q.strip()
	if UUID_RE.match(q):
		return [mb_brief(musicbrainz(f'/release/{q}', inc='artist-credits+labels+media'))]
	hits: dict[str, dict] = {}
	did = get_summary(safe(path))['discogs'] if path else ''
	if did:
		for mbid in mb_discogs_releases(did):
			try:
				brief = mb_brief(musicbrainz(f'/release/{mbid}', inc='artist-credits+labels+media'))
			except HTTPException:
				continue
			hits.setdefault(mbid, {**brief, 'match': 'Discogs ID'})
		try:
			release_tracks(did)
			d = raw_releases[did]
			barcodes = [
				re.sub(r'\D', '', i.get('value', ''))
				for i in d.get('identifiers', [])
				if i.get('type') == 'Barcode'
			]
			catnos = [
				lb['catno']
				for lb in d.get('labels', [])
				if lb.get('catno') and lb['catno'].lower() != 'none'
			]
			for code in [b for b in barcodes if b][:1]:
				mb_hits(f'barcode:{code}', 10, 'barcode', hits)
			for catno in (
				catnos[:2] if not hits else []
			):  # a barcode or Discogs ID hit is exact; the slower catalogue-number search is the fallback
				mb_hits(f'catno:"{lucene(catno)}"', 10, 'catalog number', hits)
		except HTTPException:
			pass  # no Discogs key or Discogs unreachable: the plain search below still works
	words = [w for w in re.split(r'\s+', q) if w]
	if words:
		mb_hits(
			' AND '.join(f'(release:{lucene(w)} OR artist:{lucene(w)})' for w in words),
			20,
			'',
			hits,
		)
	return list(hits.values())[:20]


def mb_release(mbid: str) -> dict:
	if mbid in mb_releases:
		return mb_releases[mbid]
	if not UUID_RE.match(mbid):
		raise HTTPException(400, 'not a MusicBrainz release ID')
	r = musicbrainz(
		f'/release/{mbid}',
		inc='artists+artist-credits+labels+recordings+release-groups+media+url-rels',
	)

	def people(credit: list[dict] | None) -> list[dict]:
		return [
			{'id': c['artist']['id'], 'name': c['artist']['name']}
			for c in credit or []
			if c.get('artist')
		]

	rg = r.get('release-group') or {}
	tracks = [
		{
			'disc': m.get('position', 1),
			'position': t.get('number', ''),
			'title': t.get('title', ''),
			'channels': channels_from_title(t.get('title', '')),
			'duration': round(t['length'] / 1000) if t.get('length') else 0,
			'artist': mb_names(t.get('artist-credit')),
			'artists': people(t.get('artist-credit')),
		}
		for m in r.get('media', [])
		for t in m.get('tracks', [])
	]
	types = [t for t in [rg.get('primary-type'), *(rg.get('secondary-types') or [])] if t]
	out = {
		**mb_brief(r),
		'artist': mb_names(r.get('artist-credit')),
		'name': r.get('title', ''),
		'artists': people(r.get('artist-credit')),
		'asin': r.get('asin') or '',
		'status': r.get('status') or '',
		'disambiguation': r.get('disambiguation') or '',
		'types': ','.join(types),
		'group': {
			'id': rg.get('id', ''),
			'title': rg.get('title', ''),
			'type': rg.get('primary-type') or '',
			'first': rg.get('first-release-date') or '',
		},
		'tracks': tracks,
		'discogs_ids': [
			m.group(1)
			for x in r.get('relations') or []
			if x.get('type') == 'discogs'
			and (m := re.search(r'/release/(\d+)', (x.get('url') or {}).get('resource', '')))
		],
	}
	mb_releases[mbid] = out
	return out


@app.get('/api/musicbrainz/release')
def musicbrainz_release(id: str, path: str = '') -> dict:
	"""The parsed release; with a path also how many files the album has."""
	return {**mb_release(id), 'files': len(flacs(safe(path))) if path else 0}


@app.get('/api/musicbrainz/check')
def musicbrainz_check(path: str) -> dict:
	"""Non-consequential notes where the album's MusicBrainz release disagrees with its Discogs release.

	Read-only and only for the selected album: it needs both IDs and one (cached) MusicBrainz lookup, which is too slow to do for a whole
	library. Compared: a Discogs link in the MusicBrainz data, the year, and the track count against the album's file count.
	"""
	album = safe(path)
	files = flacs(album)
	t0 = open_audio(files[0]).tags if files else None
	rid, mbid = (
		tag(t0 or {}, 'DISCOGS_RELEASE_ID'),
		tag(t0 or {}, 'MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID'),
	)
	if not (rid and mbid and UUID_RE.match(mbid)):
		return {'notes': []}
	mb = mb_release(mbid)
	notes = []
	if mb['discogs_ids'] and rid not in mb['discogs_ids']:
		notes.append(
			f'MusicBrainz links Discogs release {", ".join(mb["discogs_ids"])}, this album uses {rid}.'
		)
	# The year of the Discogs release itself (cached after the first request), not the year tags in the files: those
	# keep the old release's year until the next run rewrites them (ADR 0023).
	try:
		year = str(release_tracks(rid).get('year') or '')
	except HTTPException:  # Discogs unreachable: the tags are the best there is
		year = ''
	year = year or (tag(t0, 'ALBUM_RELEASE_YEAR', 'YEAR', 'DATE') or '')[:4]
	if year and mb['year'] and year != mb['year']:
		notes.append(f'Year: Discogs {year}, MusicBrainz {mb["year"]}.')
	if mb['tracks'] and len(mb['tracks']) != len(files):
		notes.append(
			f'The MusicBrainz release has {len(mb["tracks"])} tracks, this album has {len(files)} files.'
		)
	return {'notes': notes}


@app.post('/api/musicbrainz/apply')
def musicbrainz_apply(body: dict) -> dict:
	"""Write the release ID and its MusicBrainz links (release group, album artists) to every file of the album.

	Per file the artist ID and link are written only when the file's TITLE equals exactly one release track.
	Barcode, ASIN, country, status, type and disambiguation fill only empty tags.
	"""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	rel = mb_release(str(body.get('id', '')).strip().lower())
	group, mb = rel['group'], 'https://musicbrainz.org'
	by_title: dict[str, list[dict]] = {}
	for t in rel['tracks']:
		by_title.setdefault(norm_title(t['title']), []).append(t)
	values = {
		'MUSICBRAINZ_ALBUMID': [rel['id']],
		'MUSICBRAINZ_ALBUM_URL': [f'{mb}/release/{rel["id"]}'],
		'MUSICBRAINZ_RELEASE_GROUPID': [group['id']] if group['id'] else [],
		'MUSICBRAINZ_RELEASE_GROUP_URL': [f'{mb}/release-group/{group["id"]}']
		if group['id']
		else [],
		'MUSICBRAINZ_ALBUMARTISTID': [a['id'] for a in rel['artists']],
		'MUSICBRAINZ_ALBUMARTIST_URL': [f'{mb}/artist/{a["id"]}' for a in rel['artists']],
	}
	# Filled only where the tag is empty (a Discogs assignment or the owner may have set them): player tags and the tagger's descriptive tags.
	fill = {
		'BARCODE': rel['barcode'],
		'ASIN': rel['asin'],
		'MUSICBRAINZ_ALBUM_RELEASECOUNTRY': rel['country'],
		'MUSICBRAINZ_ALBUMSTATUS': rel['status'],
		'MUSICBRAINZ_ALBUMTYPE': rel['types'],
		'MUSICBRAINZ_ALBUM_DISAMBIGUATION': rel['disambiguation'],
	}
	filled: dict[str, int] = {}
	log, per_file = [], 0
	for f in flacs(album):
		a = open_audio(f)
		if a.tags is None:
			a.add_tags()
		for k in [k for k in a.tags.keys() if k.upper() in MB_ALBUM_KEYS]:
			del a.tags[k]
		for k, v in values.items():
			if v:
				a[k] = v
		for k, v in fill.items():
			if v and not tag(a.tags, k):
				a[k] = [v]
				filled[k] = filled.get(k, 0) + 1
		match = by_title.get(norm_title(tag(a.tags, 'TITLE')), [])
		if len(match) == 1 and match[0]['artists']:
			for k in [k for k in a.tags.keys() if k.upper() in MB_TRACK_KEYS]:
				del a.tags[k]
			a['MUSICBRAINZ_ARTISTID'] = [x['id'] for x in match[0]['artists']]
			a['MUSICBRAINZ_ARTIST_URL'] = [f'{mb}/artist/{x["id"]}' for x in match[0]['artists']]
			per_file += 1
		a.save()
	log.append(
		f'MusicBrainz release {rel["id"]} ({rel["artist"]} - {rel["name"]}) written; release group, album artist links on every file, artist links on {per_file} files'
	)
	if filled:
		log.append(
			'filled from MusicBrainz (only where empty): '
			+ ', '.join(f'{k} x{v}' for k, v in filled.items())
		)
	logging.getLogger('app').info(
		'MusicBrainz release %s applied to %s', body.get('id', ''), album.name
	)
	return {'log': log, 'album': fresh_summary(album)}


@app.get('/api/lrclib/search')
def lrclib_search(title: str, artist: str = '') -> list[dict]:
	"""Search lrclib.net for lyrics (read-only; nothing is written). Returns up to 20 results with their lyrics."""
	if not title.strip():
		raise HTTPException(400, 'enter a title to search for')
	q = {'track_name': title.strip(), **({'artist_name': artist.strip()} if artist.strip() else {})}
	req = urllib.request.Request(
		'https://lrclib.net/api/search?' + urlencode(q),
		headers=lrclib.headers(),
	)
	try:
		with urllib.request.urlopen(req, timeout=15) as r:
			found = json.load(r)
	except urllib.error.HTTPError as e:
		raise HTTPException(502, f'lrclib.net answered HTTP {e.code}') from e
	except (urllib.error.URLError, TimeoutError, ValueError) as e:
		raise HTTPException(502, f'lrclib.net could not be reached: {e}') from e
	return [
		{
			'artist': x.get('artistName') or '',
			'title': x.get('trackName') or '',
			'album': x.get('albumName') or '',
			'duration': round(x.get('duration') or 0),
			'instrumental': bool(x.get('instrumental')),
			'synced': x.get('syncedLyrics') or '',
			'plain': x.get('plainLyrics') or '',
		}
		for x in found[:20]
	]


# Album tags that fixtags reads as user input (it never overwrites them) and may therefore be edited here.
# The override keys are also applied to ALBUMARTIST / ALBUM so the change shows before the next run.
ALBUM_FIELDS = {
	'ALBUM_ARTIST_OVERRIDE': ('ALBUMARTIST',),
	'ALBUM_TITLE_OVERRIDE': ('ALBUM',),
	'ALBUM_FORMAT': (),
	'ALBUM_EDITION': (),
	'CATALOGNUMBER': CATALOG_KEYS[1:],
	'MUSICBRAINZ_ALBUMID': ('MUSICBRAINZ ALBUM ID',),
}
OVERRIDES = {'ALBUM_ARTIST_OVERRIDE': 'ALBUMARTIST', 'ALBUM_TITLE_OVERRIDE': 'ALBUM'}
# Tags the Discogs tags step writes (pipeline/fixtags.py; tests/test_tag_contract.py keeps both in line); shown read-only.
DISCOGS_FIXED = (
	'DATE',
	'YEAR',
	'RELEASEDATE',
	'ORIGINALDATE',
	'ORIGINALRELEASEDATE',
	'ORIGINAL DATE',
	'ORIGINAL YEAR',
	'ALBUM',
	'VERSION',
	'ALBUM_MASTER_TITLE',
	'ALBUM_RELEASE_TITLE',
	'ORIGINAL_TITLE',
	'ALBUM_MASTER_YEAR',
	'ALBUM_RELEASE_YEAR',
	'ALBUM_MAX_RESOLUTION',
	'ALBUM_RELEASE_COUNTRY',
	'ALBUM_RELEASE_LABEL',
	'ALBUM_RELEASE_LABELS',
	'ALBUM_RELEASE_CATALOGNUMBERS',
	'ALBUM_RELEASE_FORMAT',
	'ALBUM_RELEASE_FORMAT_DESCRIPTIONS',
	'ALBUM_RELEASE_FORMAT_TEXT',
	'ALBUM_RELEASE_GENRES',
	'ALBUM_RELEASE_STYLES',
	'ALBUM_RELEASE_NOTES',
	'ALBUM_RELEASE_DATE_FULL',
	'ALBUM_RELEASE_DATA_QUALITY',
	'ALBUM_RELEASE_SERIES',
	'ALBUM_DR',
)
DISCOGS_PREFIXES = (*DISCOGS_TAG_PREFIXES, 'DISCOGS_')


def other_tags(files: list[Path]) -> list[dict]:
	"""Every tag the other tabs of the tag editor do not show (ADR 0057): key, the first file's value, in how many files
	it is set and whether the values differ. Read-only."""
	shown = {
		*ALBUM_FIELDS,
		*(
			a
			for alts in ALBUM_FIELDS.values()
			if alts != ('ALBUMARTIST',) and alts != ('ALBUM',)
			for a in alts
		),
		*CATALOG_KEYS,
		*DISCOGS_FIXED,
		'TITLE',
		'ARTIST',
		'TRACKNUMBER',
		'DISCNUMBER',
		'DISCSUBTITLE',
		'SET SUBTITLE',
		'LYRICS',  # edited per track, with its own editor
		'BARCODE',
		'ASIN',
	}
	seen: dict[str, list[str]] = {}
	count: dict[str, int] = {}
	for f in files:
		for k, v in (open_audio(f).tags or {}).items():
			key = k.upper()
			if key in shown or key.startswith(('MUSICBRAINZ', *DISCOGS_PREFIXES)):
				continue
			value = ' / '.join(str(x) for x in v)
			seen.setdefault(key, []).append(value)
			count[key] = count.get(key, 0) + 1
	return [
		{
			'key': k,
			'value': vals[0],
			'files': count[k],
			'of': len(files),
			'varies': len(set(vals)) > 1,
		}
		for k, vals in sorted(seen.items())
	]


@app.get('/api/tags')
def get_tags(path: str) -> dict:
	album = safe(path)
	files = flacs(album)
	if not files:
		raise HTTPException(404, 'no flac files')
	t0 = open_audio(files[0]).tags or {}
	keys = {k.upper(): k for k in t0.keys()}
	fixed = [k for k in DISCOGS_FIXED if k in keys]
	extra = sorted(k for k in keys if k.startswith(DISCOGS_PREFIXES) and k != 'DISCOGS_RELEASE_ID')
	# read-only MusicBrainz tags (written by the MusicBrainz apply, 0023); the release ID itself is an Album-tab field
	mb = sorted(
		k
		for k in keys
		if k.startswith('MUSICBRAINZ') and k not in ('MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID')
	)
	mb += [k for k in ('BARCODE', 'ASIN') if k in keys]
	tracks = []
	for f in files:
		audio = open_audio(f)
		t = audio.tags or {}
		tracks.append(
			{
				'file': str(f.relative_to(album)),
				'channels': audio.info.channels,
				'title': tag(t, 'TITLE'),
				'artist': tag(t, 'ARTIST'),
				'disc': tag(t, 'DISCNUMBER'),
				'track': tag(t, 'TRACKNUMBER'),
				'subtitle': tag(t, 'SET SUBTITLE'),
			}
		)
	return {
		'other': other_tags(files),
		'fields': {
			k: tag(t0, k) if k in OVERRIDES else tag(t0, k, *alts)
			for k, alts in ALBUM_FIELDS.items()
		},  # an override shows only when really set
		'discogs_id': tag(t0, 'DISCOGS_RELEASE_ID'),
		'discogs': [
			{'key': k, 'value': ' / '.join(str(v) for v in t0[keys[k]])} for k in [*fixed, *extra]
		],
		'musicbrainz': [{'key': k, 'value': ' / '.join(str(v) for v in t0[keys[k]])} for k in mb],
		'album_artist': tag(t0, 'ALBUMARTIST'),
		'tracks': tracks,
	}


def discogs_defaults(rid: str) -> dict[str, str]:
	"""What fixtags would derive from Discogs for ALBUMARTIST and ALBUM: release artists, master title (else release title)."""
	r = discogs(f'/releases/{rid}')
	title = r.get('title', '').strip()
	if r.get('master_id'):
		try:
			title = discogs(f'/masters/{r["master_id"]}').get('title', title).strip()
		except HTTPException:
			pass  # fixtags falls back to the release title as well
	return {'ALBUMARTIST': artist_names(r.get('artists', [])), 'ALBUM': title}


def write_album_fields(album: Path, fields: dict) -> bool:
	"""Write album-level fields to every file; blank removes. Clearing an override that is set restores the Discogs value."""
	files = flacs(album)
	first = open_audio(files[0]).tags or {}
	clearing = [
		k for k in OVERRIDES if k in fields and not str(fields[k]).strip() and tag(first, k)
	]
	restore = {}
	if clearing:
		rid = tag(first, 'DISCOGS_RELEASE_ID')
		if not rid:
			raise HTTPException(
				400, 'cannot restore the Discogs value: the album has no Discogs release ID'
			)
		restore = discogs_defaults(rid)  # before touching any file: a failed lookup changes nothing
	# VERSION (year, DR, format, edition, catalogue number) and the folder name derive from these. It is removed here
	# and rewritten at once by the caller (ADR 0049); if that cannot be done the missing VERSION reopens the Tags
	# step (ADR 0006) until the next run.
	stale = bool(tag(first, 'DISCOGS_RELEASE_ID')) and any(
		k in fields and str(fields[k]).strip() != tag(first, k, *ALBUM_FIELDS[k])
		for k in ('ALBUM_EDITION', 'ALBUM_FORMAT', 'CATALOGNUMBER')
	)
	for f in files:
		a = open_audio(f)
		if a.tags is None:
			a.add_tags()
		if stale and 'VERSION' in a.tags:
			del a.tags['VERSION']
		for key, value in fields.items():
			value = str(value).strip()
			if value:
				a[key] = [value]
				if key in OVERRIDES:
					a[OVERRIDES[key]] = [value]
			elif key in OVERRIDES:
				if key in a.tags:
					del a.tags[key]
					if restore.get(OVERRIDES[key]):
						a[OVERRIDES[key]] = [restore[OVERRIDES[key]]]
			else:
				for k in (key, *ALBUM_FIELDS[key]):
					if k in a.tags:
						del a.tags[k]
		a.save()
	return stale


@app.post('/api/tags')
def set_tags(body: dict) -> dict:
	"""Write edited album fields to every file and edited per-track fields to the listed files; rename to match titles."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	for tr in body.get('tracks', []):  # checked before anything is written
		if not all(str(tr.get(k, '')).strip() for k in ('title', 'disc', 'track')):
			raise HTTPException(400, f'title, disc and track must not be empty ({tr.get("file")})')
	fields = {k: v for k, v in body.get('fields', {}).items() if k in ALBUM_FIELDS}
	if 'CATALOGNUMBER' in fields and not str(fields['CATALOGNUMBER']).strip():
		raise HTTPException(400, "Add a catalog number (enter 'none' if the release has none).")
	if 'ALBUM_FORMAT' in fields and not str(fields['ALBUM_FORMAT']).strip():
		raise HTTPException(400, 'album format must not be empty (for example CD, SACD, Vinyl)')
	stale = write_album_fields(album, fields) if fields else False
	log = [f'album: {k} = {v or "(removed)"}' for k, v in fields.items()]
	for tr in body.get('tracks', []):
		a = open_audio(track_path(body.get('path', ''), tr.get('file', '')))
		if a.tags is None:
			a.add_tags()
		a['TITLE'] = [str(tr['title']).strip()]
		a['DISCNUMBER'] = [str(tr['disc']).strip()]
		a['TRACKNUMBER'] = [str(tr['track']).strip()]
		for key, field in (('ARTIST', 'artist'), ('SET SUBTITLE', 'subtitle')):
			value = str(tr.get(field, '')).strip()
			if value:
				a[key] = [value]
			elif key in a.tags:
				del a.tags[key]
		sub = str(tr.get('subtitle', '')).strip()
		if sub:
			a['DISCSUBTITLE'] = [sub]
		elif 'DISCSUBTITLE' in a.tags:
			del a.tags['DISCSUBTITLE']
		a.save()
		log.append(f'track: {tr["file"]}')
	if stale:
		log.append(refresh_discogs_tags(album))
	applog.info(
		'tags saved: %s: %s; %d track(s) edited',
		album.name,
		', '.join(f'{k}={str(v).strip()!r}' for k, v in fields.items()) or 'no album fields',
		len(body.get('tracks', [])),
	)
	for tr in body.get('tracks', []):
		applog.debug(
			'%s: %s: title=%r disc=%s track=%s artist=%r',
			album.name,
			tr.get('file'),
			tr.get('title'),
			tr.get('disc'),
			tr.get('track'),
			tr.get('artist'),
		)
	return {'log': [*log, *rename_album_files(album)], 'album': fresh_summary(album)}


@app.post('/api/overrides')
def set_overrides(body: dict) -> dict:
	"""Album artist / title overrides only (the pencil dialog); same effect as the Tag Editor fields."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	write_album_fields(
		album,
		{
			'ALBUM_ARTIST_OVERRIDE': body.get('artist', ''),
			'ALBUM_TITLE_OVERRIDE': body.get('title', ''),
		},
	)
	return fresh_summary(album)


class Static(StaticFiles):
	"""Static files revalidated on every load, so a rebuilt frontend is never served stale from the browser cache."""

	async def get_response(self, path: str, scope: Scope) -> Response:
		r = await super().get_response(path, scope)
		r.headers['Cache-Control'] = 'no-cache'
		return r


app.mount('/static', Static(directory=Path(__file__).parent / 'static'), name='static')


@app.get('/')
def index() -> FileResponse:
	# no-cache like the static files: after a rebuild the page must not point at chunks that are gone
	return FileResponse(
		Path(__file__).parent / 'static' / 'ui' / 'index.html',
		headers={'Cache-Control': 'no-cache'},
	)


if __name__ == '__main__':
	logconfig.configure(os.environ)
	log.info('Tagwright started: staging %s, library %s', ROOT, INGEST)
	uvicorn.run(
		app,
		host='0.0.0.0',
		port=int(os.environ.get('PORT', '8080')),
		log_config=logconfig.uvicorn_config(),
	)
