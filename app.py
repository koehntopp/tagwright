#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = ["fastapi", "uvicorn", "mutagen", "python-slugify", "unidecode", "pathvalidate", "pillow"]
# ///
"""Tagwright: web UI over the discogs nzbfix pipeline.

Env: ROOT (base dir, default /staging), INGEST_DIR (default /flac/ingest),
DISCOGS_DIR (dir holding nzbfix.py, default /opt/discogs), PORT (8080).
"""

import io
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from mutagen.flac import FLAC, Picture
from PIL import Image, UnidentifiedImageError
from pathvalidate import sanitize_filename
from slugify import slugify

def env_path(name: str, default: str) -> Path:
	"""Read a path from the environment; ~ is expanded, relative paths are a startup error."""
	p = Path(os.environ.get(name, default)).expanduser()
	if not p.is_absolute():
		raise SystemExit(f'{name}={p} must be an absolute path (missing leading slash?)')
	return p.resolve()


ROOT = env_path('ROOT', '/staging')
INGEST = env_path('INGEST_DIR', '/flac/ingest')
SCRIPTS = env_path('DISCOGS_DIR', '/opt/discogs')
DATA = env_path('DATA_DIR', str(Path(__file__).parent / 'data'))  # settings.json and generated config overlay
SETTINGS_FILE = DATA / 'settings.json'
KEYS = ('discogs_api_key', 'lrclib_api_key')
settings: dict = {}
if SETTINGS_FILE.is_file():
	settings = json.loads(SETTINGS_FILE.read_text())
	ROOT = Path(settings.get('input') or ROOT)
	INGEST = Path(settings.get('output') or INGEST)
DISC_RE = re.compile(r'^(?:Disc|CD)\s*\d+$', re.I)  # same rule as discogs disc_layout.DISC_DIR_RE
CATALOG_KEYS = ('CATALOGNUMBER', 'CATALOG NUMBER', 'CATALOG_NUMBER', 'CATALOGNO')  # spellings fixtags reads, first present wins
# One entry per required tag (alternative spellings together); an empty one means the album is not ready.
REQUIRED_TAGS = (('ARTIST',), ('ALBUMARTIST',), ('TITLE',), ('ALBUM',), ('TRACKNUMBER',), ('DISCNUMBER',), ('ALBUM_FORMAT',), CATALOG_KEYS)
MIN_COVER = int(settings.get('min_cover', 1400))  # px, either side; a smaller or missing cover blocks the album; 0 turns the check off


def cover_note(cov: dict | None) -> str:
	return f'Cover is {cov["w"]}x{cov["h"]}, below the minimum {MIN_COVER}x{MIN_COVER}.' if cov else 'The album has no cover.'

SYNCED_RE = re.compile(r'\[\d{2}:\d{2}\.\d{2}\]')  # strict [MM:SS.xx], as in the discogs lrc_count.py
INSTRUMENTAL_RE = re.compile(r'\[instrumental:true\]|\[\d{2}:\d{2}\.\d{2}\]\s*(?:\[instrumental\]|\(instrumental\))', re.I)

app = FastAPI()
job = {'path': None, 'state': 'idle', 'lines': [], 'rc': None, 'queue': [], 'stop': False, 'proc': None}  # lines accumulate across runs
lock = threading.Lock()


def safe(p: str) -> Path:
	"""Resolve p and require it under ROOT (trust boundary for every endpoint)."""
	path = Path(p).resolve()
	if path != ROOT and ROOT not in path.parents:
		raise HTTPException(400, 'path outside root')
	return path


def flacs(album: Path) -> list[Path]:
	return sorted(album.rglob('*.flac'))


def album_dirs(base: Path) -> list[Path]:
	found = set()
	for f in base.rglob('*.flac'):
		d = f.parent
		found.add(d.parent if DISC_RE.match(d.name) else d)
	return sorted(found)


def tag(t, *keys) -> str:
	for k in keys:
		v = t.get(k)
		if v:
			return v[0]
	return ''


def clean(text: str) -> str:
	"""Same rule as discogs bliss.clean(); keep in sync (bliss.py imports config and syslog logging, so not imported)."""
	return sanitize_filename(slugify(text, lowercase=False, separator='_'))


def bliss_name(t) -> str | None:
	"""Bliss file name <disc>_<track>_<title>.flac, or None while TITLE, TRACKNUMBER or DISCNUMBER is empty.

	An empty tag means the album is not ready; nothing is invented (no "Unknown Title", no track 00, no disc 01).
	"""
	title, number, disc = tag(t, 'TITLE'), tag(t, 'TRACKNUMBER'), tag(t, 'DISCNUMBER')
	if not title or not number or not disc:
		return None
	return f'{disc.split("/")[0].zfill(2)}_{number.split("/")[0].zfill(2)}_{clean(title)}.flac'


def bliss_album(t) -> str:
	"""Bliss library path <album artist>/<album [version]>, or '' while ALBUMARTIST or ALBUM is empty (not ready)."""
	album, artist = tag(t, 'ALBUM'), tag(t, 'ALBUMARTIST')
	if not album or not artist:
		return ''
	ver = tag(t, 'VERSION')
	if ver and ver not in album:
		album = f'{album} {ver}'
	return f'{clean(artist)}/{clean(album)}'


def same_name(a: str, b: str) -> bool:
	n = lambda x: unicodedata.normalize('NFD', x.lower())  # noqa: E731
	return n(a) == n(b)


def rename_files(album: Path) -> list[str]:
	"""Rename FLACs in place to the bliss pattern. Returns log lines."""
	out = []
	for f in flacs(album):
		new = bliss_name(FLAC(f).tags or {})
		if new is None:
			out.append(f'skip {f.name}: title or track number is empty')
			continue
		if f.name == new:
			continue
		dest = f.with_name(new)
		if dest.exists() and not same_name(str(dest), str(f)):
			out.append(f'skip {f.name}: {new} already exists')
			continue
		f.rename(dest)
		out.append(f'renamed {f.name} -> {new}')
	return out or ['filenames already match']


def lyric_kind(t) -> str:
	"""instr (instrumental marker, or no lyrics with language zxx), lrc (synced), txt (plain) or none."""
	ly = tag(t, 'LYRICS')
	if not ly.strip():
		return 'instr' if tag(t, 'LYRICS_LANGUAGE') == 'zxx' else 'none'
	if INSTRUMENTAL_RE.search(ly):  # before lrc: the canonical block contains [00:00.00]
		return 'instr'
	return 'lrc' if SYNCED_RE.search(ly) else 'txt'


def track_dr_mean(tags) -> str:
	"""Album DR fallback: mean of the per-track DYNAMIC_RANGE tags."""
	vals = [int(v) for t in tags if (v := tag(t, 'DYNAMIC_RANGE')).isdigit() and int(v) > 0]
	return str(round(sum(vals) / len(vals))).zfill(2) if vals else ''


def track_files(album: Path, files, tags, lengths, has_discogs: bool) -> list[dict]:
	"""Per-track rows; checks[i] answers pipeline step i (same order as steps in summarize)."""
	out = []
	for f, t, length in zip(files, tags, lengths):
		kind = lyric_kind(t)
		tags_ok = has_discogs and all(tag(t, *k) for k in REQUIRED_TAGS) and bool(tag(t, 'DATE', 'YEAR'))
		out.append({
			'name': f.name,
			'length': round(length),
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
				f.name == bliss_name(t),
			],
		})
	return out


def cover_info(a: FLAC, album: Path) -> dict | None:
	"""Size of the cover that /api/cover serves (embedded front cover first, else a folder image)."""
	pics = a.pictures
	pic = next((p for p in pics if p.type == 3), pics[0] if pics else None)
	if pic:
		w, h = pic.width, pic.height
		if not (w and h):  # some taggers leave the dimensions unset
			try:
				with Image.open(io.BytesIO(pic.data)) as im:
					w, h = im.width, im.height
			except (OSError, UnidentifiedImageError):
				pass
		return {'w': w, 'h': h, 'bytes': len(pic.data), 'embedded': True}
	for name in ('cover.jpg', 'folder.jpg', 'cover.png', 'folder.png'):
		img = album / name
		if img.is_file():
			try:
				with Image.open(img) as im:
					return {'w': im.width, 'h': im.height, 'bytes': img.stat().st_size, 'embedded': False}
			except (OSError, UnidentifiedImageError):
				return None
	return None


def summarize(album: Path) -> dict:
	files = flacs(album)
	if not files:
		raise HTTPException(404, 'no flac files')
	audio = [FLAC(f) for f in files]
	tags = [a.tags or {} for a in audio]
	t0 = tags[0]
	did = tag(t0, 'DISCOGS_RELEASE_ID')
	mid = tag(t0, 'MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID')
	out = {
		'path': str(album),
		'name': album.name,
		'artist': tag(t0, 'ALBUMARTIST', 'ARTIST'),
		'artist_is_albumartist': bool(tag(t0, 'ALBUMARTIST')),
		'new_title': bliss_album(t0),
		'album': tag(t0, 'ALBUM'),
		'cover': cover_info(audio[0], album),
		'artist_override': tag(t0, 'ALBUM_ARTIST_OVERRIDE'),
		'title_override': tag(t0, 'ALBUM_TITLE_OVERRIDE'),
		'year': tag(t0, 'DATE', 'YEAR')[:4],
		'discogs': did,
		'mbid': mid,
		'tracks': len(files),
		'edition': ' · '.join(x for x in (tag(t0, 'VERSION'), tag(t0, 'CATALOGNUMBER')) if x),
		'mtime': max(f.stat().st_mtime for f in files),
	}
	n = len(tags)
	have = lambda *k: sum(1 for t in tags if tag(t, *k)) == n  # noqa: E731
	kinds = [lyric_kind(t) for t in tags]
	syn, pla, ins, mis = (kinds.count(k) for k in ('lrc', 'txt', 'instr', 'none'))
	req = all(have(*k) for k in REQUIRED_TAGS) and have('DATE', 'YEAR')
	cov = out['cover']
	small_cover = MIN_COVER > 0 and (not cov or cov['w'] < MIN_COVER or cov['h'] < MIN_COVER)
	steps = [
		('Dynamic range', have('DYNAMIC_RANGE')),
		('ReplayGain', have('REPLAYGAIN_ALBUM_GAIN')),
		('Fingerprints', have('ACOUSTID_FINGERPRINT', 'ACOUSTID FINGERPRINT')),
		('Tags and cover', bool(did) and req),
		('Lyrics', mis == 0),
		('Filenames', all(f.name == bliss_name(t) for f, t in zip(files, tags))),  # None (not ready) never equals a name
	]
	out.update(
		dr=tag(t0, 'ALBUM_DR') or track_dr_mean(tags),
		files=track_files(album, files, tags, [a.info.length for a in audio], bool(did)),
		lyrics={'synced': syn, 'plain': pla, 'instrumental': ins, 'missing': mis},
		# partial = done but worth a look (yellow, still counts as done): some lyrics are plain text only, or the cover is small
		steps=[{'name': a, 'done': b, 'partial': b and ((a == 'Lyrics' and pla > 0) or (a == 'Tags and cover' and small_cover)),
			'note': cover_note(cov) if a == 'Tags and cover' and small_cover else ''} for a, b in steps],
		tags_ok=req,
		steps_done=sum(1 for _, ok in steps if ok),
	)
	out['issues'] = album_issues(out, tags, small_cover)
	out['status'] = status(out)
	return out


def count_text(n: int, total: int, what: str) -> str:
	if n == total:
		return f'No track has {what}.' if total > 1 else f'The track has no {what.split(" ", 1)[-1]}.'
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
	'album artist': 'Set the album artist.', 'catalog number': "Add a catalog number (enter 'none' if the release has none).",
	'album format': 'Set the album format (for example CD, SACD, Vinyl).',
}


def album_issues(out: dict, tags: list, small_cover: bool) -> list[dict]:
	"""Clearly identifiable problems, one line each: {text, action, level}; recomputed from the tags on every refresh.

	level 'warn' blocks the album (status needs), 'ingest' blocks only the move to ingest, 'info' is a notice. action tells the UI which button to offer.
	"""
	n, issues = len(tags), []
	missing = lambda *keys: sum(1 for t in tags if not tag(t, *keys))  # noqa: E731
	if not out['discogs']:
		issues.append({'text': 'Add a Discogs release ID before running fixes.', 'action': 'search', 'level': 'warn'})
	for label, keys, action, required in ALBUM_LEVEL:
		values = [tag(t, *keys) for t in tags]
		if required and (m := values.count('')) and not (label == 'Discogs release ID' and m == n):  # all empty: the Discogs line above
			text = MISSING_TEXT[label] if m == n else f'{m} of {n} tracks have no {label}.'
			issues.append({'text': text, 'action': action, 'level': 'warn'})
		filled = [v for v in values if v]
		if len(set(filled)) > 1:
			issues.append({'text': f'The files disagree on the {label} ({len(set(filled))} different values); it is read from the first file only.', 'action': action, 'level': 'warn'})
		elif not required and filled and len(filled) < n:  # a gap in a required tag is reported above
			issues.append({'text': f'The {label} is set on only {len(filled)} of {n} tracks; it is read from the first file only.', 'action': action, 'level': 'warn'})
	for key, what in (('DISCNUMBER', 'a disc number'), ('TRACKNUMBER', 'a track number'), ('TITLE', 'a title'), ('ARTIST', 'an artist')):
		if m := missing(key):
			issues.append({'text': count_text(m, n, what), 'action': 'tracks', 'level': 'warn'})
	numbers = [(tag(t, 'DISCNUMBER').split('/')[0], tag(t, 'TRACKNUMBER').split('/')[0]) for t in tags if tag(t, 'DISCNUMBER') and tag(t, 'TRACKNUMBER')]
	if dup := sum(1 for v in {x: numbers.count(x) for x in numbers}.values() if v > 1):
		issues.append({'text': f'{dup} disc/track number{" is" if dup == 1 else "s are"} used by more than one file.', 'action': 'tracks', 'level': 'warn'})
	if small_cover:
		issues.append({'text': cover_note(out['cover']), 'action': 'cover', 'level': 'ingest'})
	return issues


def status(s: dict) -> str:
	"""needs: a blocking issue (no Discogs id, an empty required tag, files that disagree); fixed: all steps done; else ready."""
	if any(i['level'] == 'warn' for i in s['issues']):
		return 'needs'
	return 'fixed' if s['steps_done'] == len(s['steps']) else 'ready'


cache: dict[str, tuple[tuple, dict]] = {}


def get_summary(album: Path) -> dict:
	"""summarize() cached by (file names, mtimes, sizes); reading tags of a whole library is slow on network volumes."""
	files = flacs(album)
	sig = tuple((f.name, st.st_mtime_ns, st.st_size) for f in files for st in [f.stat()])
	hit = cache.get(str(album))
	if hit and hit[0] == sig:
		return hit[1]
	s = summarize(album)
	cache[str(album)] = (sig, s)
	return s


@app.get('/api/dirs')
def dirs(path: str = ''):
	p = safe(path) if path else ROOT
	subs = sorted(d.name for d in p.iterdir() if d.is_dir() and not d.name.startswith('.'))
	return {'path': str(p), 'root': str(ROOT), 'dirs': subs}


def safe_summary(a: Path) -> dict:
	try:
		return get_summary(a)
	except Exception as e:  # noqa: BLE001  # one unreadable album must not break the list
		return {'path': str(a), 'name': a.name, 'discogs': '', 'mbid': '', 'status': 'needs', 'steps_done': 0, 'steps': [], 'tracks': 0, 'mtime': 0, 'error': str(e)}


@app.get('/api/albums')
def albums(path: str = ''):
	base = safe(path) if path else ROOT
	with ThreadPoolExecutor(8) as ex:
		res = list(ex.map(safe_summary, album_dirs(base)))
	res.sort(key=lambda s: s['mtime'], reverse=True)
	return {'base': str(base), 'albums': res}


@app.get('/api/album')
def album(path: str):
	return get_summary(safe(path))


def make_picture(data: bytes) -> Picture:
	"""Front-cover Picture from image bytes; JPEG and PNG are kept, anything else becomes JPEG (400 if unreadable)."""
	try:
		with Image.open(io.BytesIO(data)) as im:
			fmt, w, h, mode = im.format, im.width, im.height, im.mode
			if fmt not in ('JPEG', 'PNG'):  # FLAC players expect JPEG or PNG
				buf = io.BytesIO()
				im.convert('RGB').save(buf, 'JPEG', quality=95)
				data, fmt, mode = buf.getvalue(), 'JPEG', 'RGB'
	except (OSError, UnidentifiedImageError) as e:
		raise HTTPException(400, 'not a readable image') from e
	pic = Picture()
	pic.type, pic.mime, pic.desc, pic.width, pic.height, pic.data = 3, f'image/{fmt.lower()}', '', w, h, data
	pic.depth = {'1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32}.get(mode, 24)
	return pic


def embed_cover(album: Path, pic: Picture, only_missing: bool = False) -> None:
	"""Replace the front and untyped covers of every file (back cover etc. stay); only_missing: files without any picture."""
	for f in flacs(album):
		a = FLAC(f)
		if only_missing and a.pictures:
			continue
		keep = [p for p in a.pictures if p.type not in (0, 3)]
		a.clear_pictures()
		a.add_picture(pic)
		for p in keep:
			a.add_picture(p)
		a.save()


@app.put('/api/cover')
async def set_cover(path: str, request: Request):
	"""Replace the embedded front cover of every file with the uploaded image (raw request body)."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(path)
	embed_cover(album, make_picture(await request.body()))
	return get_summary(album)


@app.get('/api/cover')
def cover(path: str):
	album = safe(path)
	for f in flacs(album)[:1]:
		pics = FLAC(f).pictures
		pic = next((p for p in pics if p.type == 3), pics[0] if pics else None)
		if pic:
			return Response(pic.data, media_type=pic.mime or 'image/jpeg')
	for name in ('cover.jpg', 'folder.jpg', 'cover.png', 'folder.png'):
		img = album / name
		if img.is_file():
			return FileResponse(img)
	return Response(status_code=204)  # no art: 204 keeps the browser console free of 404s


def overlay_env(env: dict) -> None:
	"""Point CONFIG_DIR at a generated copy of the scripts' config.py with the API keys from settings appended.

	log.py puts CONFIG_DIR first on sys.path, so the scripts import this copy and the original stays untouched.
	"""
	if not any(settings.get(k) for k in KEYS):
		return
	orig = Path(os.environ.get('CONFIG_DIR', SCRIPTS)) / 'config.py'
	text = orig.read_text() if orig.is_file() else ''
	extra = ''.join(f'\n{k} = {settings[k]!r}' for k in KEYS if settings.get(k))
	d = DATA / 'overlay'
	d.mkdir(parents=True, exist_ok=True)
	f = d / 'config.py'
	f.write_text(f'{text}\n# tagwright settings overrides{extra}\n')
	f.chmod(0o600)
	env['CONFIG_DIR'] = str(d)


def runner(path: Path):
	"""Run nzbfix for one album, then rename files. Returns the exit code."""
	env = {**os.environ, 'LOG_LEVEL': 'INFO'}
	overlay_env(env)
	job['path'] = str(path)
	job['lines'].append(f'=== {path.name} ===')
	try:
		p = subprocess.Popen(
			[str(SCRIPTS / 'nzbfix.py'), str(path)],
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=SCRIPTS,
			start_new_session=True,  # own process group, so Stop can end nzbfix and the tools it started
		)
		job['proc'] = p
		for line in p.stdout:
			job['lines'].append(line.rstrip())
		rc = p.wait()
		if job['stop']:
			job['lines'].append('-- stopped by user')
		elif rc == 0:
			job['lines'].append('-- rename files')
			job['lines'].extend(rename_files(path))
	except Exception as e:  # noqa: BLE001  # surface launch failures in the log pane
		job['lines'].append(f'launch failed: {e}')
		rc = -1
	return rc


def worker(paths: list[Path]):
	"""Process the queue one album at a time; a failure is logged and the queue continues."""
	failed = 0
	for p in paths:
		if job['stop']:
			break
		job['queue'] = [str(x) for x in paths[paths.index(p) + 1:]]
		if runner(p) != 0:
			failed += 1
	job.update(queue=[], proc=None, rc=1 if failed else 0, state='stopped' if job['stop'] else 'failed' if failed else 'done')


@app.post('/api/run')
def run(body: dict):
	"""Body: {path} for one album or {paths: [...]} for a queue (Run all ready)."""
	raw = body.get('paths') or [body.get('path', '')]
	paths = [safe(p) for p in raw]
	for path in paths:
		if get_summary(path)['status'] == 'needs':
			raise HTTPException(409, f'{path.name} is not ready: fix the problems listed for it first')
	with lock:  # one heavy task at a time
		if job['state'] == 'running':
			raise HTTPException(409, 'a job is already running')
		job.update(path=str(paths[0]), state='running', rc=None, stop=False, proc=None, queue=[str(x) for x in paths[1:]])
	threading.Thread(target=worker, args=(paths,), daemon=True).start()
	return {'ok': True, 'count': len(paths)}


@app.post('/api/stop')
def stop():
	"""Stop the running job: clear the queue and end nzbfix with everything it started (SIGTERM, SIGKILL after 10 s)."""
	with lock:
		if job['state'] != 'running':
			raise HTTPException(409, 'no job is running')
		job['stop'] = True
		job['queue'] = []
		p = job['proc']

	def end(sig):
		try:
			os.killpg(p.pid, sig)  # start_new_session made the group id the pid
		except ProcessLookupError:
			pass

	if p and p.poll() is None:
		end(signal.SIGTERM)
		threading.Timer(10, lambda: p.poll() is None and end(signal.SIGKILL)).start()
	return {'ok': True}


def hint(v: str) -> str:
	return '\u2022' * 4 + v[-4:] if v else ''


@app.get('/api/settings')
def get_settings():
	return {'input': str(ROOT), 'output': str(INGEST), 'min_cover': MIN_COVER, **{k + '_hint': hint(settings.get(k, '')) for k in KEYS}}


@app.post('/api/settings')
def set_settings(body: dict):
	"""Blank key keeps the stored key; {clear_<key>: true} removes it."""
	global ROOT, INGEST, MIN_COVER
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	try:
		new_min = int(body.get('min_cover', MIN_COVER))
	except (TypeError, ValueError) as e:
		raise HTTPException(400, 'Minimum cover size must be a whole number of pixels') from e
	if not 0 <= new_min <= 20000:
		raise HTTPException(400, 'Minimum cover size must be between 0 and 20000 pixels')
	new_in = Path(str(body.get('input') or ROOT)).expanduser()
	new_out = Path(str(body.get('output') or INGEST)).expanduser()
	for label, p in (('Input folder', new_in), ('Output folder', new_out)):
		if not p.is_absolute():
			raise HTTPException(400, f'{label} must be an absolute path')
	if not new_in.is_dir():
		raise HTTPException(400, 'Input folder does not exist')
	settings.update(input=str(new_in.resolve()), output=str(new_out.resolve()), min_cover=new_min)
	for k in KEYS:
		if body.get('clear_' + k):
			settings.pop(k, None)
		elif str(body.get(k) or '').strip():
			settings[k] = str(body[k]).strip()
	DATA.mkdir(parents=True, exist_ok=True)
	SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
	SETTINGS_FILE.chmod(0o600)
	ROOT, INGEST, MIN_COVER = Path(settings['input']), Path(settings['output']), new_min
	cache.clear()
	return get_settings()


@app.get('/api/job')
def get_job(since: int = 0):
	return {**{k: job[k] for k in ('path', 'state', 'rc', 'queue')}, 'lines': job['lines'][since:], 'next': len(job['lines'])}


@app.post('/api/move')
def move(body: dict):
	path = safe(body.get('path', ''))
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	if path == ROOT or not path.is_dir():
		raise HTTPException(400, 'not an album folder')
	s = get_summary(path)
	if s['status'] != 'fixed':
		raise HTTPException(409, 'album is not fully fixed')
	if any(i['level'] == 'ingest' for i in s['issues']):
		raise HTTPException(409, 'cover is below the minimum size; replace it or lower the minimum in settings')
	dest = INGEST / path.name
	if dest.exists():
		raise HTTPException(409, f'{dest} already exists')
	INGEST.mkdir(parents=True, exist_ok=True)
	shutil.move(str(path), str(dest))
	return {'moved_to': str(dest)}


# ---------- track editor: assign album files to a Discogs release ----------
releases: dict[str, dict] = {}  # release id -> parsed tracklist (Discogs allows 60 requests/min)
raw_releases: dict[str, dict] = {}  # release id -> the Discogs release JSON, for the tags written on apply


def discogs_key() -> str:
	if settings.get('discogs_api_key'):
		return settings['discogs_api_key']
	cfg = Path(os.environ.get('CONFIG_DIR', SCRIPTS)) / 'config.py'
	m = re.search(r'^discogs_api_key\s*=\s*[\'"]([^\'"]+)', cfg.read_text(), re.M) if cfg.is_file() else None
	return m.group(1) if m else ''


# Same rate-limit handling as the discogs repository (find_audiophile_upgrades: min_interval 1.1 s and a 5 s pause when
# X-Discogs-Ratelimit-Remaining drops below 3; fixtags.discogs_fetch and ADR 0001 section 6: a 429 or an empty body is
# retried up to 3 times after 60 s). Discogs allows 60 requests a minute, so requests are sent one at a time, at least
# 1.1 s apart, and the waits are shared (the lock is held) so concurrent calls do not pause and then burst together.
discogs_lock = threading.Lock()
DISCOGS_INTERVAL, DISCOGS_LOW_PAUSE, DISCOGS_RETRIES, DISCOGS_BACKOFF = 1.1, 5.0, 3, 60.0
discogs_last = 0.0  # time the last request ended; guarded by discogs_lock


def discogs_wait() -> None:
	time.sleep(max(0.0, DISCOGS_INTERVAL - (time.time() - discogs_last)))


def discogs_done(headers) -> None:
	global discogs_last
	discogs_last = time.time()
	remaining = headers.get('X-Discogs-Ratelimit-Remaining') if headers else None
	if remaining and remaining.isdigit() and int(remaining) < 3:
		time.sleep(DISCOGS_LOW_PAUSE)


def discogs(path: str, **params) -> dict:
	key = discogs_key()
	if not key:
		raise HTTPException(400, 'Discogs API key not set (Settings)')
	url = 'https://api.discogs.com' + path + ('?' + urlencode(params) if params else '')
	req = urllib.request.Request(url, headers={'User-Agent': 'Tagwright/0.2', 'Authorization': f'Discogs token={key}'})
	with discogs_lock:
		for attempt in range(DISCOGS_RETRIES + 1):
			discogs_wait()
			try:
				with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
					data = json.load(r)
					discogs_done(r.headers)
				return data
			except urllib.error.HTTPError as e:
				discogs_done(e.headers)
				if e.code == 404:
					raise HTTPException(404, 'Discogs: not found') from e
				if e.code != 429:
					raise HTTPException(502, f'Discogs: HTTP {e.code}') from e
				err = HTTPException(429, 'Discogs rate limit reached; try again in a minute')
			except json.JSONDecodeError:  # an empty body is how Discogs sometimes signals the limit
				err = HTTPException(502, 'Discogs sent an empty response; try again in a minute')
			except OSError as e:
				raise HTTPException(502, f'Discogs: {e}') from e
			if attempt < DISCOGS_RETRIES:
				time.sleep(DISCOGS_BACKOFF)
			else:
				raise err


def discogs_image(url: str) -> bytes:
	"""Download a release image with the same pacing as API calls (one request at a time, 1.1 s apart)."""
	req = urllib.request.Request(url, headers={'User-Agent': 'Tagwright/0.2', 'Authorization': f'Discogs token={discogs_key()}'})
	with discogs_lock:
		discogs_wait()
		try:
			with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
				data = r.read(20_000_001)
				discogs_done(r.headers)
		except (urllib.error.URLError, OSError) as e:
			raise HTTPException(502, f'Discogs image: {e}') from e
	if len(data) > 20_000_000:
		raise HTTPException(502, 'Discogs image is too large')
	return data


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


WRITER_ROLES = ('written-by', 'written by', 'composed by', 'music by', 'songwriter', 'lyrics by', 'words by')
COPYRIGHT_TYPES = ('copyright (c)', 'phonographic copyright (p)')


def clean_artist(name: str) -> str:
	return re.sub(r'\s*\(\d+\)$', '', name.strip())


def uniq(xs) -> list[str]:
	return list(dict.fromkeys(x for x in xs if x))


def by_role(extra: list[dict], *roles: str) -> list[str]:
	"""Names of the credits whose role contains one of the (lower-case) role words."""
	return uniq(clean_artist(e.get('name', '')) for e in extra if any(w in (e.get('role') or '').lower() for w in roles))


def release_tags(r: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
	"""(player tags, DISCOGS_* tags) from a raw Discogs release. Empty values are omitted.

	Player tags are the standard ones the tagger used to import (shown by Roon etc.); they are filled when missing.
	DISCOGS_* tags are Discogs-owned and replaced on every assignment.
	"""
	extra, companies, labels = r.get('extraartists') or [], r.get('companies') or [], r.get('labels') or []
	artists = r.get('artists') or []

	def company(*types: str) -> list[str]:
		return uniq(clean_artist(c.get('name', '')) for c in companies if (c.get('entity_type_name') or '').lower() in types)

	fmts = ', '.join(
		f['name'] + (f' ({",".join(f["descriptions"])})' if f.get('descriptions') else '') for f in r.get('formats') or [] if f.get('name')
	)
	catnos = uniq((lb.get('catno') or '').strip() for lb in labels if (lb.get('catno') or '').strip().lower() != 'none')
	barcode = next((i['value'].strip() for i in r.get('identifiers') or [] if i.get('type') == 'Barcode' and i.get('value')), '')
	copyright_ = [f'\u2117 {n}' for n in company('phonographic copyright (p)')] + [f'\u00a9 {n}' for n in company('copyright (c)')]
	player = {
		'GENRE': uniq(r.get('genres') or []),
		'MOOD': [', '.join(r.get('styles') or [])],  # the tagger put the Discogs styles here
		'LABEL': uniq(clean_artist(lb.get('name', '')) for lb in labels),
		'MEDIA': [fmts], 'COUNTRY': [r.get('country', '')], 'BARCODE': [barcode], 'CATALOG': catnos,
		'COPYRIGHT': [', '.join(copyright_)], 'PUBLISHER': [', '.join(company('published by'))],
		'PRODUCER': by_role(extra, 'producer'), 'ENGINEER': by_role(extra, 'engineer'),
		'PERSONNEL': uniq(f'{clean_artist(e["name"])} - {e["role"]}' for e in extra if e.get('name') and e.get('role')),
	}
	rid = r['id']
	artist_urls = [f'https://www.discogs.com/artist/{a["id"]}' for a in artists if a.get('id')]
	discogs_tags = {
		'DISCOGS_RELEASE_URL': [r.get('uri', '')],
		'DISCOGS_MASTER_ID': [f'm{r["master_id"]}'] if r.get('master_id') else [],
		'DISCOGS_MASTER_URL': [f'https://www.discogs.com/master/{r["master_id"]}'] if r.get('master_id') else [],
		'DISCOGS_ARTIST_URL': artist_urls, 'DISCOGS_ALBUMARTIST_URL': artist_urls,
		'DISCOGS_ARTIST_LIST': [', '.join(clean_artist(a.get('name', '')) for a in artists)],
		'DISCOGS_LABEL_URL': [f'https://www.discogs.com/label/{lb["id"]}' for lb in labels if lb.get('id')],
		'DISCOGS_ARTWORK_URL': [f'https://www.discogs.com/viewimages?release={rid}'],
		'DISCOGS_CATALOG_NUMBER': uniq(f'{clean_artist(lb.get("name", ""))}: {lb["catno"]}' for lb in labels if lb.get('catno')),
		'DISCOGS_ALBUM_RELEASECOUNTRY': [r.get('country', '')],
		'DISCOGS_RELEASE_NOTES': [(r.get('notes') or '').strip()],
		'DISCOGS_VIDEO_URL': uniq(f'{v.get("title", "").strip()}: {v["uri"]}' for v in r.get('videos') or [] if v.get('uri')),
	}
	for c in companies:  # Recorded At, Mixed At, Pressed By, ... one tag per role
		role = (c.get('entity_type_name') or '').strip()
		if role and role.lower() not in COPYRIGHT_TYPES:
			key = 'DISCOGS_' + re.sub(r'[^A-Z0-9]+', '_', role.upper()).strip('_')
			discogs_tags.setdefault(key, [])
			name = clean_artist(c.get('name', ''))
			if name and name not in discogs_tags[key]:
				discogs_tags[key].append(name)
	for key in [k for k in discogs_tags if k.startswith('DISCOGS_') and k not in DISCOGS_FIXED_KEYS]:
		discogs_tags[key] = [', '.join(discogs_tags[key])] if discogs_tags[key] else []
	return ({k: [x for x in v if x] for k, v in player.items() if any(v)}, {k: [x for x in v if x] for k, v in discogs_tags.items() if any(v)})


# DISCOGS_* tags that keep one value per entry instead of one joined value (the rest are per company role)
DISCOGS_FIXED_KEYS = {
	'DISCOGS_RELEASE_URL', 'DISCOGS_MASTER_ID', 'DISCOGS_MASTER_URL', 'DISCOGS_ARTIST_URL', 'DISCOGS_ALBUMARTIST_URL', 'DISCOGS_ARTIST_LIST',
	'DISCOGS_LABEL_URL', 'DISCOGS_ARTWORK_URL', 'DISCOGS_CATALOG_NUMBER', 'DISCOGS_ALBUM_RELEASECOUNTRY', 'DISCOGS_RELEASE_NOTES', 'DISCOGS_VIDEO_URL',
}


def release_tracks(rid: str) -> dict:
	if rid in releases:
		return releases[rid]
	r = discogs(f'/releases/{rid}')
	album_artist = artist_names(r.get('artists', []))
	tracks, seq = [], 0
	for t in r.get('tracklist', []):
		if t.get('type_') != 'track':
			continue
		pos = t.get('position', '')
		m = re.match(r'^(?:CD|DVD)?(\d+)[-.](\d+)$', pos, re.I)
		seq += 1
		tracks.append({
			'i': len(tracks), 'position': pos, 'disc': int(m[1]) if m else 1, 'track': int(m[2]) if m else seq,
			'title': t.get('title', ''), 'duration': seconds(t.get('duration', '')),
			'artist': artist_names(t.get('artists', [])) or album_artist,
			'composers': by_role(t.get('extraartists') or [], *WRITER_ROLES),
			'producers': by_role(t.get('extraartists') or [], 'producer'),
			'engineers': by_role(t.get('extraartists') or [], 'engineer'),
		})
	# Discogs' own 'none' counts: the tag must not be empty
	catno = next((c for lb in r.get('labels', []) if (c := (lb.get('catno') or '').strip())), '')
	images = r.get('images') or []
	image = next((i for i in images if i.get('type') == 'primary'), images[0] if images else {}).get('uri', '')
	out = {
		'id': str(r['id']), 'title': r.get('title', ''), 'artist': album_artist, 'year': r.get('year', ''), 'catno': catno,
		'master_id': r.get('master_id') or 0, 'image': image, 'tracks': tracks,
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
		'id': str(r['id']), 'title': title, 'year': r.get('year', ''), 'country': r.get('country', ''),
		'format': ', '.join(fmt[:3]), 'label': ', '.join(label[:2]),
		'catno': r.get('catno') or (r.get('labels') or [{}])[0].get('catno', ''), 'thumb': r.get('thumb', ''),
	}


@app.get('/api/discogs/search')
def discogs_search(q: str):
	q = q.strip()
	if q.isdigit():
		return [brief(discogs(f'/releases/{q}'))]
	return [brief(r) for r in discogs('/database/search', type='release', q=q, per_page=20).get('results', [])]


@app.get('/api/discogs/tracks')
def discogs_tracks(id: str):
	"""Track count of a release (cached with the parsed tracklist)."""
	return {'count': len(release_tracks(id.strip())['tracks'])}


def norm_title(s: str) -> str:
	return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()).strip()


def album_files(album: Path) -> list[dict]:
	out = []
	for f in flacs(album):
		a = FLAC(f)
		t = a.tags or {}
		out.append({
			'file': str(f.relative_to(album)), 'title': tag(t, 'TITLE') or f.stem, 'duration': round(a.info.length),
			'disc': int(m[0]) if (m := re.match(r'\d+', tag(t, 'DISCNUMBER') or '1')) else 1,
			'track': int(m[0]) if (m := re.match(r'\d+', tag(t, 'TRACKNUMBER'))) else 0,
		})
	return sorted(out, key=lambda x: (x['disc'], x['track'], x['file']))


@app.post('/api/tracks/propose')
def tracks_propose(body: dict):
	"""Release tracklist, album files and a suggested file -> release track assignment."""
	album = safe(body.get('path', ''))
	rel = release_tracks(str(body.get('release_id', '')).strip())
	files = album_files(album)
	pairs = []
	for f in files:
		for t in rel['tracks']:
			s = SequenceMatcher(None, norm_title(f['title']), norm_title(t["title"])).ratio() * 0.6
			if t['duration']:
				s += max(0.0, 1 - abs(f['duration'] - t['duration']) / 8) * 0.25
			if f['track'] and (f['disc'], f['track']) == (t['disc'], t['track']):
				s += 0.15
			pairs.append((s, f['file'], t['i']))
	assign: dict[str, int | None] = {f['file']: None for f in files}
	conf: dict[str, float] = {}
	used: set[int] = set()
	for s, fn, i in sorted(pairs, reverse=True):
		if s >= 0.35 and assign[fn] is None and i not in used:
			assign[fn], conf[fn] = i, round(s, 2)
			used.add(i)
	return {'release': rel, 'files': [{**f, 'rel': assign[f['file']], 'conf': conf.get(f['file'], 0)} for f in files]}


@app.post('/api/tracks/apply')
def tracks_apply(body: dict):
	"""Write release id and per-track tags for the assigned files, then rename them (bliss pattern).

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
			final[a['file']] = (int(a.get('disc') or final[a['file']][0]), int(a.get('track') or final[a['file']][1]))
		except (TypeError, ValueError) as e:
			raise HTTPException(400, 'disc and track must be numbers') from e
	per_disc: dict[int, int] = {}
	for d, _ in final.values():
		per_disc[d] = per_disc.get(d, 0) + 1
	log = []
	filled: dict[str, int] = {}

	def fill(a: FLAC, key: str, value: str | list[str], *alts: str) -> None:
		# Tags the tagger used to import from Discogs (the pipeline reads some as user input): filled when empty,
		# never overwritten (discogs ADR 0002 section 1 and 2).
		values = [value] if isinstance(value, str) else value
		if values and not tag(a.tags, key, *alts):
			a[key] = values
			filled[key] = filled.get(key, 0) + 1

	player, discogs_tags = release_tags(raw_releases[rel['id']])
	writers = by_role(raw_releases[rel['id']].get('extraartists') or [], *WRITER_ROLES)

	cover = None
	if not FLAC(flacs(album)[0]).pictures and rel['image']:
		try:
			cover = make_picture(discogs_image(rel['image']))
		except HTTPException as e:
			log.append(f'cover not fetched: {e.detail}')
	for fn, i in picked:
		t = rel['tracks'][i]
		d, n = final[fn]
		a = FLAC(album / fn)
		if a.tags is None:
			a.add_tags()
		a['DISCOGS_RELEASE_ID'] = [rel['id']]
		fill(a, 'CATALOGNUMBER', rel['catno'], *CATALOG_KEYS[1:])
		fill(a, 'ARTIST', t['artist'])
		if not tag(a.tags, 'ALBUM_ARTIST_OVERRIDE'):
			fill(a, 'ALBUMARTIST', rel['artist'])
		if not tag(a.tags, 'ALBUM_TITLE_OVERRIDE') and not tag(a.tags, 'ALBUM'):
			fill(a, 'ALBUM', release_album_title(rel))
		for key, values in player.items():
			if key not in ('PRODUCER', 'ENGINEER'):
				fill(a, key, values)
		fill(a, 'COMPOSER', t['composers'] or writers)  # track credits win over release credits
		fill(a, 'PRODUCER', t['producers'] or player.get('PRODUCER', []))
		fill(a, 'ENGINEER', t['engineers'] or player.get('ENGINEER', []))
		for key in [k for k in a.tags.keys() if k.upper().startswith('DISCOGS_') and k.upper() != 'DISCOGS_RELEASE_ID']:
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
	log.append(f'Discogs-owned tags written: {len(discogs_tags) + 1} per file')
	if filled:
		log.append('filled from Discogs: ' + ', '.join(f'{k} x{v}' if v > 1 else k for k, v in filled.items()))
	log += rename_files(album)
	return {'log': log, 'album': get_summary(album)}


def track_path(album: str, file: str) -> Path:
	f = safe(str(safe(album) / file))
	if f.suffix.lower() != '.flac' or not f.is_file():
		raise HTTPException(404, 'no such track')
	return f


@app.get('/api/audio')
def audio(path: str, file: str):
	return FileResponse(track_path(path, file), media_type='audio/flac')


@app.get('/api/track')
def get_track(path: str, file: str):
	t = FLAC(track_path(path, file)).tags or {}
	return {'title': tag(t, 'TITLE'), 'lyrics': tag(t, 'LYRICS')}


@app.post('/api/track')
def set_track(body: dict):
	"""Edit title and lyrics of one file; the file is renamed to match the new title."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	a = FLAC(track_path(body.get('path', ''), body.get('file', '')))
	if a.tags is None:
		a.add_tags()
	title, lyrics = str(body.get('title', '')).strip(), str(body.get('lyrics', ''))
	if not title:
		raise HTTPException(400, 'title must not be empty')
	a['TITLE'] = [title]
	if lyrics.strip():
		a['LYRICS'] = [lyrics.strip('\n')]
	elif 'LYRICS' in a.tags:
		del a.tags['LYRICS']
	a.save()
	return {'log': [f'edited {body["file"]}', *rename_files(album)], 'album': get_summary(album)}


# Album tags that fixtags reads as user input (it never overwrites them) and may therefore be edited here.
# The override keys are also applied to ALBUMARTIST / ALBUM so the change shows before the next run.
ALBUM_FIELDS = {
	'ALBUM_ARTIST_OVERRIDE': ('ALBUMARTIST',), 'ALBUM_TITLE_OVERRIDE': ('ALBUM',), 'ALBUM_FORMAT': (), 'ALBUM_EDITION': (),
	'CATALOGNUMBER': CATALOG_KEYS[1:], 'MUSICBRAINZ_ALBUMID': ('MUSICBRAINZ ALBUM ID',),
}
OVERRIDES = {'ALBUM_ARTIST_OVERRIDE': 'ALBUMARTIST', 'ALBUM_TITLE_OVERRIDE': 'ALBUM'}
# Tags fixtags writes from the Discogs release (see discogs/fixtags.py); shown read-only.
DISCOGS_FIXED = (
	'DATE', 'YEAR', 'RELEASEDATE', 'ORIGINALDATE', 'ORIGINALRELEASEDATE', 'ORIGINAL DATE', 'ORIGINAL YEAR', 'ALBUM', 'VERSION',
	'ALBUM_MASTER_TITLE', 'ALBUM_RELEASE_TITLE', 'ORIGINAL_TITLE', 'ALBUM_MASTER_YEAR', 'ALBUM_RELEASE_YEAR', 'ALBUM_MAX_RESOLUTION',
	'ALBUM_RELEASE_COUNTRY', 'ALBUM_RELEASE_LABEL', 'ALBUM_RELEASE_LABELS', 'ALBUM_RELEASE_CATALOGNUMBERS', 'ALBUM_RELEASE_FORMAT',
	'ALBUM_RELEASE_FORMAT_DESCRIPTIONS', 'ALBUM_RELEASE_FORMAT_TEXT', 'ALBUM_RELEASE_GENRES', 'ALBUM_RELEASE_STYLES',
	'ALBUM_RELEASE_NOTES', 'ALBUM_RELEASE_DATE_FULL', 'ALBUM_RELEASE_DATA_QUALITY', 'ALBUM_RELEASE_SERIES', 'ALBUM_DR',
)
DISCOGS_PREFIXES = ('ALBUM_COMPANY_', 'ALBUM_CREDIT_', 'ALBUM_IDENT_', 'DISCOGS_')


@app.get('/api/tags')
def get_tags(path: str):
	album = safe(path)
	files = flacs(album)
	if not files:
		raise HTTPException(404, 'no flac files')
	t0 = FLAC(files[0]).tags or {}
	keys = {k.upper(): k for k in t0.keys()}
	fixed = [k for k in DISCOGS_FIXED if k in keys]
	extra = sorted(k for k in keys if k.startswith(DISCOGS_PREFIXES) and k != 'DISCOGS_RELEASE_ID')
	tracks = []
	for f in files:
		t = FLAC(f).tags or {}
		tracks.append({
			'file': str(f.relative_to(album)), 'title': tag(t, 'TITLE'), 'artist': tag(t, 'ARTIST'),
			'disc': tag(t, 'DISCNUMBER'), 'track': tag(t, 'TRACKNUMBER'), 'subtitle': tag(t, 'SET SUBTITLE'),
		})
	return {
		'fields': {k: tag(t0, k, *alts) for k, alts in ALBUM_FIELDS.items()},
		'discogs_id': tag(t0, 'DISCOGS_RELEASE_ID'),
		'discogs': [{'key': k, 'value': ' / '.join(str(v) for v in t0[keys[k]])} for k in [*fixed, *extra]],
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


def write_album_fields(album: Path, fields: dict) -> None:
	"""Write album-level fields to every file; blank removes. Clearing an override that is set restores the Discogs value."""
	files = flacs(album)
	first = FLAC(files[0]).tags or {}
	clearing = [k for k in OVERRIDES if k in fields and not str(fields[k]).strip() and tag(first, k)]
	restore = {}
	if clearing:
		rid = tag(first, 'DISCOGS_RELEASE_ID')
		if not rid:
			raise HTTPException(400, 'cannot restore the Discogs value: the album has no Discogs release ID')
		restore = discogs_defaults(rid)  # before touching any file: a failed lookup changes nothing
	for f in files:
		a = FLAC(f)
		if a.tags is None:
			a.add_tags()
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


@app.post('/api/tags')
def set_tags(body: dict):
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
	if fields:
		write_album_fields(album, fields)
	log = [f'album: {k} = {v or "(removed)"}' for k, v in fields.items()]
	for tr in body.get('tracks', []):
		a = FLAC(track_path(body.get('path', ''), tr.get('file', '')))
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
	return {'log': [*log, *rename_files(album)], 'album': get_summary(album)}


@app.post('/api/overrides')
def set_overrides(body: dict):
	"""Album artist / title overrides only (the pencil dialog); same effect as the Tag Editor fields."""
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	album = safe(body.get('path', ''))
	write_album_fields(album, {'ALBUM_ARTIST_OVERRIDE': body.get('artist', ''), 'ALBUM_TITLE_OVERRIDE': body.get('title', '')})
	return get_summary(album)


app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')


@app.get('/')
def index():
	return FileResponse(Path(__file__).parent / 'index.html')


if __name__ == '__main__':
	uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))  # noqa: S104
