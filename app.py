#!/usr/bin/env -S uv run
# /// script
# dependencies = ["fastapi", "uvicorn", "mutagen", "python-slugify", "unidecode", "pathvalidate"]
# ///
"""Albumfixer: web UI over the discogs nzbfix pipeline.

Env: ROOT (base dir, default /staging), INGEST_DIR (default /flac/ingest),
DISCOGS_DIR (dir holding nzbfix.py, default /opt/discogs), PORT (8080).
"""

import json
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import unicodedata
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from mutagen.flac import FLAC
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
DISC_RE = re.compile(r'^(disc|cd)\s*\d+$', re.I)
SYNCED_RE = re.compile(r'\[\d+:\d+')

app = FastAPI()
job = {'path': None, 'state': 'idle', 'lines': [], 'rc': None, 'queue': []}  # lines accumulate across runs
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


def bliss_name(t) -> str:
	"""Bliss file name: <disc>_<track>_<title>.flac."""
	disc = (tag(t, 'DISCNUMBER') or '01').split('/')[0].zfill(2)
	track = (tag(t, 'TRACKNUMBER') or '00').split('/')[0].zfill(2)
	return f'{disc}_{track}_{clean(tag(t, "TITLE") or "Unknown Title")}.flac'


def bliss_album(t) -> str:
	"""Bliss library path: <album artist>/<album [version]>."""
	album = tag(t, 'ALBUM') or 'Unknown Album'
	ver = tag(t, 'VERSION')
	if ver and ver not in album:
		album = f'{album} {ver}'
	return f'{clean(tag(t, "ALBUMARTIST", "ARTIST") or "Unknown Artist")}/{clean(album)}'


def same_name(a: str, b: str) -> bool:
	n = lambda x: unicodedata.normalize('NFD', x.lower())  # noqa: E731
	return n(a) == n(b)


def rename_files(album: Path) -> list[str]:
	"""Rename FLACs in place to the bliss pattern. Returns log lines."""
	out = []
	for f in flacs(album):
		new = bliss_name(FLAC(f).tags or {})
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
	"""lrc (synced), txt (plain), instr (zxx marker, no lyrics) or none."""
	ly = tag(t, 'LYRICS')
	if SYNCED_RE.search(ly):
		return 'lrc'
	if ly.strip():
		return 'txt'
	return 'instr' if tag(t, 'LYRICS_LANGUAGE') == 'zxx' else 'none'


def track_dr_mean(tags) -> str:
	"""Album DR fallback: mean of the per-track DYNAMIC_RANGE tags."""
	vals = [int(v) for t in tags if (v := tag(t, 'DYNAMIC_RANGE', 'DYNAMIC RANGE')).isdigit() and int(v) > 0]
	return str(round(sum(vals) / len(vals))).zfill(2) if vals else ''


def track_files(files, tags, has_discogs: bool) -> list[dict]:
	"""Per-track rows; checks[i] answers pipeline step i (same order as steps in summarize)."""
	out = []
	for f, t in zip(files, tags):
		kind = lyric_kind(t)
		tags_ok = has_discogs and all(tag(t, k) for k in ('ARTIST', 'TITLE', 'ALBUM', 'TRACKNUMBER')) and bool(tag(t, 'DATE', 'YEAR'))
		out.append({
			'name': f.name,
			'disc': tag(t, 'DISCNUMBER'),
			'track': tag(t, 'TRACKNUMBER'),
			'title': tag(t, 'TITLE') or f.stem,
			'dr': tag(t, 'DYNAMIC_RANGE', 'DYNAMIC RANGE'),
			'lyrics': kind,
			'checks': [
				bool(tag(t, 'DYNAMIC_RANGE', 'DYNAMIC RANGE')),
				bool(tag(t, 'REPLAYGAIN_ALBUM_GAIN')),
				bool(tag(t, 'ACOUSTID_FINGERPRINT', 'ACOUSTID FINGERPRINT')),
				tags_ok,
				kind != 'none',
				f.name == bliss_name(t),
			],
		})
	return out


def summarize(album: Path) -> dict:
	files = flacs(album)
	if not files:
		raise HTTPException(404, 'no flac files')
	tags = [FLAC(f).tags or {} for f in files]
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
		'year': tag(t0, 'DATE', 'YEAR')[:4],
		'discogs': did,
		'mbid': mid,
		'tracks': len(files),
		'edition': ' · '.join(x for x in (tag(t0, 'VERSION'), tag(t0, 'CATALOGNUMBER')) if x),
		'mtime': max(f.stat().st_mtime for f in files),
	}
	n = len(tags)
	have = lambda *k: sum(1 for t in tags if tag(t, *k)) == n  # noqa: E731
	syn = pla = ins = mis = 0
	for t in tags:
		ly = tag(t, 'LYRICS')
		if SYNCED_RE.search(ly):
			syn += 1
		elif ly.strip():
			pla += 1
		elif tag(t, 'LYRICS_LANGUAGE') == 'zxx':
			ins += 1
		else:
			mis += 1
	req = all(have(k) for k in ('ARTIST', 'TITLE', 'ALBUM', 'TRACKNUMBER')) and have('DATE', 'YEAR')
	steps = [
		('Dynamic range', have('DYNAMIC_RANGE', 'DYNAMIC RANGE')),
		('ReplayGain', have('REPLAYGAIN_ALBUM_GAIN')),
		('Fingerprints', have('ACOUSTID_FINGERPRINT', 'ACOUSTID FINGERPRINT')),
		('Tags and cover', bool(did) and req),
		('Lyrics', mis == 0),
		('Filenames', all(f.name == bliss_name(t) for f, t in zip(files, tags))),
	]
	out.update(
		dr=tag(t0, 'ALBUM_DR') or track_dr_mean(tags),
		files=track_files(files, tags, bool(did)),
		lyrics={'synced': syn, 'plain': pla, 'instrumental': ins, 'missing': mis},
		steps=[{'name': a, 'done': b, 'partial': a == 'Lyrics' and b and pla > 0} for a, b in steps],  # partial: lyrics complete but some only plain text; still counts as done
		tags_ok=req,
		steps_done=sum(1 for _, ok in steps if ok),
	)
	out['status'] = status(out)
	return out


def status(s: dict) -> str:
	"""needs: no Discogs id (fixtags requires it); fixed: all steps done; else ready."""
	if not s['discogs']:
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
	f.write_text(f'{text}\n# albumfixer settings overrides{extra}\n')
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
		)
		for line in p.stdout:
			job['lines'].append(line.rstrip())
		rc = p.wait()
		if rc == 0:
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
		job['queue'] = [str(x) for x in paths[paths.index(p) + 1:]]
		if runner(p) != 0:
			failed += 1
	job.update(queue=[], rc=1 if failed else 0, state='failed' if failed else 'done')


@app.post('/api/run')
def run(body: dict):
	"""Body: {path} for one album or {paths: [...]} for a queue (Run all ready)."""
	raw = body.get('paths') or [body.get('path', '')]
	paths = [safe(p) for p in raw]
	with lock:  # one heavy task at a time
		if job['state'] == 'running':
			raise HTTPException(409, 'a job is already running')
		job.update(path=str(paths[0]), state='running', rc=None, queue=[str(x) for x in paths[1:]])
	threading.Thread(target=worker, args=(paths,), daemon=True).start()
	return {'ok': True, 'count': len(paths)}


def hint(v: str) -> str:
	return '\u2022' * 4 + v[-4:] if v else ''


@app.get('/api/settings')
def get_settings():
	return {'input': str(ROOT), 'output': str(INGEST), **{k + '_hint': hint(settings.get(k, '')) for k in KEYS}}


@app.post('/api/settings')
def set_settings(body: dict):
	"""Blank key keeps the stored key; {clear_<key>: true} removes it."""
	global ROOT, INGEST
	if job['state'] == 'running':
		raise HTTPException(409, 'a job is running')
	new_in = Path(str(body.get('input') or ROOT)).expanduser()
	new_out = Path(str(body.get('output') or INGEST)).expanduser()
	for label, p in (('Input folder', new_in), ('Output folder', new_out)):
		if not p.is_absolute():
			raise HTTPException(400, f'{label} must be an absolute path')
	if not new_in.is_dir():
		raise HTTPException(400, 'Input folder does not exist')
	settings.update(input=str(new_in.resolve()), output=str(new_out.resolve()))
	for k in KEYS:
		if body.get('clear_' + k):
			settings.pop(k, None)
		elif str(body.get(k) or '').strip():
			settings[k] = str(body[k]).strip()
	DATA.mkdir(parents=True, exist_ok=True)
	SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
	SETTINGS_FILE.chmod(0o600)
	ROOT, INGEST = Path(settings['input']), Path(settings['output'])
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
	dest = INGEST / path.name
	if dest.exists():
		raise HTTPException(409, f'{dest} already exists')
	INGEST.mkdir(parents=True, exist_ok=True)
	shutil.move(str(path), str(dest))
	return {'moved_to': str(dest)}


app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')


@app.get('/')
def index():
	return FileResponse(Path(__file__).parent / 'index.html')


if __name__ == '__main__':
	uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))  # noqa: S104
