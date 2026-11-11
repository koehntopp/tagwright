"""The watcher: one thread that keeps the library folder in the canonical layout (ADR 0037).

Each pass scans (cheaply, see scanner.py), plans (planner.py) and, with Apply on, moves what has settled. A file
or album is left alone until nothing in it has changed for the cooldown, so half-copied albums and tags that a
tag editor is still writing are never acted on. With Apply off the watcher only reports what it would do.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from library import planner
from library.executor import Executor
from library.index import Index
from library.planner import Item, Problem
from library.scanner import Reader, read_tags, scan
from library.template import Template, default, validate

log = logging.getLogger(__name__)

MAX_LISTED = 200  # problems and planned moves kept for the UI


@dataclass(frozen=True)
class Settings:
	apply: bool = True  # move files; off = report only
	cooldown: float = 60.0  # seconds without any change before an album is acted on
	interval: float = 120.0  # seconds between quick passes
	sweep_hours: float = 24.0  # a full pass (stats every file) at least this often
	template: Template = field(default_factory=default)


class Library:
	def __init__(
		self,
		root: Callable[[], Path | None],
		index_path: Path | str,
		settings: Callable[[], Settings],
		clock: Callable[[], float] = time.time,
		reader: Reader = read_tags,
	) -> None:
		self._root_of = root
		self._settings_of = settings
		self._index_path = index_path
		self._clock = clock
		self._reader = reader
		self._index: Index | None = None
		self._root: Path | None = None
		self._stop = threading.Event()
		self._wake = threading.Event()
		self._thread: threading.Thread | None = None
		self._full_requested = True  # the first pass after start is a full one
		self._last_full = 0.0
		self.exclusive = (
			threading.RLock()
		)  # held while files are moved, also by "Move to library" (ADR 0008)
		self._lock = threading.Lock()
		self._state: dict = {
			'phase': 'starting',
			'message': '',
			'error': '',
			'artists': 0,
			'albums': 0,
			'tracks': 0,
			'planned': [],
			'waiting': 0,
			'unplaced': [],
			'skipped': [],
			'recent': deque(maxlen=100),
			'last_scan': 0.0,
			'last_full': 0.0,
			'next_wake': 0.0,
		}

	# --- control
	def start(self) -> None:
		if self._thread and self._thread.is_alive():
			return
		self._stop.clear()
		self._thread = threading.Thread(target=self._loop, name='library', daemon=True)
		self._thread.start()

	def stop(self) -> None:
		self._stop.set()
		self._wake.set()
		if self._thread:
			self._thread.join(10)

	def rescan(self) -> None:
		"""Re-analyse everything: a full pass now, ignoring what the index remembers about directories."""
		self._full_requested = True
		self._wake.set()

	def poke(self) -> None:
		"""Run a quick pass soon (settings changed, a file was added by Tagwright itself)."""
		self._wake.set()

	# --- status
	def _set(self, **kw: object) -> None:
		with self._lock:
			self._state.update(kw)

	def _note(self, text: str) -> None:
		with self._lock:
			self._state['recent'].appendleft({'t': self._clock(), 'text': text})

	def status(self) -> dict:
		with self._lock:
			s = dict(self._state)
			s['recent'] = list(s['recent'])
		cfg = self._settings_of()
		s.update(
			root=str(self._root or ''),
			apply=cfg.apply,
			cooldown=cfg.cooldown,
			interval=cfg.interval,
		)
		return s

	# --- one pass
	def _open(self, root: Path) -> Index:
		if self._index is None:
			self._index = Index(self._index_path)
		if self._root != root:
			if self._root is not None:
				self._index.clear()  # another folder: nothing of the old one applies
			self._root = root
			self._full_requested = True
		return self._index

	def cycle(self, full: bool = False) -> None:
		"""One pass: scan, plan, and (with Apply) move what has settled."""
		root = self._root_of()
		cfg = self._settings_of()
		if root is None or not root.is_dir():
			self._set(
				phase='error', error='The output folder is not set or does not exist.', message=''
			)
			return
		errors, _ = validate(cfg.template)
		if errors:
			self._set(
				phase='error',
				error='The path template is invalid: ' + '; '.join(errors),
				message='',
			)
			return
		index = self._open(root)
		now = self._clock()
		full = full or self._full_requested or now - self._last_full >= cfg.sweep_hours * 3600
		self._full_requested = False
		self._set(phase='scanning', error='', message='scanning' + (' (full)' if full else ''))
		stats = scan(
			root,
			index,
			now,
			full,
			self._reader,
			should_stop=self._stop.is_set,
			progress=lambda m: self._set(message=m),
		)
		if stats.interrupted:
			return
		if full:
			self._last_full = now
			self._set(last_full=now)
		artists, albums, tracks = index.counts()
		self._set(
			phase='planning',
			message='planning',
			artists=artists,
			albums=albums,
			tracks=tracks,
			last_scan=now,
		)

		items = index.items()
		discs = planner.album_dirs_with_discs(i.path for i in items)
		plan = planner.plan(items, cfg.template, lambda d: d in discs)
		unreadable = index.errors()
		unplaced = [Problem(PurePosixPath(p), f'unreadable: {e}') for p, e in unreadable.items()]
		unplaced += [u for u in plan.unplaced if str(u.path) not in unreadable]

		ready, waiting, next_wake = self._settle(plan.moves, index, now, cfg.cooldown)
		self._set(
			waiting=len(waiting),
			next_wake=next_wake,
			unplaced=[{'path': str(p.path), 'reason': p.reason} for p in unplaced[:MAX_LISTED]],
			skipped=[{'path': str(p.path), 'reason': p.reason} for p in plan.skipped[:MAX_LISTED]],
			planned=[
				{'from': str(m.src), 'to': str(m.dst)} for m in (ready + waiting)[:MAX_LISTED]
			],
		)
		if cfg.apply and ready:
			self._execute(root, index, ready)
		self._set(
			phase='waiting' if waiting else 'idle',
			message=f'waiting for {len(waiting)} file(s) to settle' if waiting else '',
		)

	def _settle(
		self, moves: list[planner.Move], index: Index, now: float, cooldown: float
	) -> tuple[list, list, float]:
		"""Split moves into those that may run now and those that wait: a move waits while any file in its source
		or destination folder changed within the cooldown. Also returns when the first waiting one is ready."""
		changed, mtimes = index.changed_at(), index.mtimes()
		unsettled: dict[str, float] = {}  # folder -> the time it settles
		for path, c in changed.items():
			settles = max(c, mtimes.get(path, 0) / 1e9) + cooldown
			if settles > now:
				folder = str(PurePosixPath(path).parent)
				unsettled[folder] = max(unsettled.get(folder, 0.0), settles)
		ready, waiting, wake = [], [], 0.0
		for m in moves:
			until = max(
				unsettled.get(str(m.src.parent), 0.0), unsettled.get(str(m.dst.parent), 0.0)
			)
			if until > now:
				waiting.append(m)
				wake = until if not wake else min(wake, until)
			else:
				ready.append(m)
		return ready, waiting, wake

	def _execute(self, root: Path, index: Index, moves: list[planner.Move]) -> None:
		self._set(phase='moving', message=f'moving {len(moves)} file(s)')
		with self.exclusive:
			result = Executor(root, self._stop.is_set).run(moves)
		for old, new in result.done:
			index.move_file(old, new)
		for old_dir in result.renamed_dirs:
			index.delete_tree(old_dir)
		index.forget_dirs(result.touched)
		for text in result.actions:
			self._note(text)
		if result.sidecars:
			self._note(f'moved {result.sidecars} other file(s) with their album')
		if result.removed_dirs:
			self._note(f'removed {result.removed_dirs} empty folder(s)')
		for p in result.errors[:20]:
			self._note(f'{p.path}: {p.reason}')
		self._full_requested = False
		self._set(next_wake=self._clock() + 5)  # look again soon: the moves changed the folders

	# --- the thread
	def _delay(self) -> float:
		cfg = self._settings_of()
		wake = self._state['next_wake']
		now = self._clock()
		if wake and wake > now:
			return max(1.0, min(cfg.interval, wake - now + 0.5))
		return cfg.interval

	def _loop(self) -> None:
		while not self._stop.is_set():
			try:
				self.cycle()
			except (
				Exception
			) as e:  # the thread must not die: show it in the status and try again later
				log.exception('Library pass failed')
				self._set(phase='error', error=f'{type(e).__name__}: {e}', message='')
			self._wake.wait(self._delay())
			self._wake.clear()

	# --- helpers for the web layer
	def preview(self, template: Template, album: str | None = None) -> dict:
		"""What the template would do with one album of the library (nothing is changed): the album folder the
		files get and each file's name below it. Without `album` the first folder that has a placeable file is used."""
		errors, warnings = validate(template)
		out: dict = {
			'errors': errors,
			'warnings': warnings,
			'album': '',
			'album_dir': '',
			'files': [],
		}
		if errors or self._index is None:
			return out
		by_dir: dict[str, list[Item]] = {}
		for i in self._index.items():
			by_dir.setdefault(str(i.path.parent), []).append(i)
		candidates = [album] if album in by_dir else sorted(by_dir)
		choice, plan = '', planner.Plan()
		for d in candidates:
			p = planner.plan(by_dir[d], template)
			if p.moves or p.in_place:
				choice, plan = d, p
				break
		else:
			choice = candidates[0] if candidates else ''
			plan = planner.plan(by_dir.get(choice, []), template)
		wanted = {str(m.src): m.dst for m in plan.moves}
		problems = {str(p.path): p.reason for p in [*plan.unplaced, *plan.skipped]}
		depth = len(template.folders)
		sample = by_dir.get(choice, [])
		files = []
		for i in sample[:30]:
			dst = wanted.get(str(i.path), i.path if str(i.path) not in problems else None)
			files.append(
				{
					'from': str(i.path),
					'to': str(dst) if dst else '',
					'name': '/'.join(dst.parts[depth:]) if dst else '',
					'problem': problems.get(str(i.path), ''),
				}
			)
		placed = next((f for f in files if f['to']), None)
		out['album'] = choice
		out['album_dir'] = '/'.join(PurePosixPath(placed['to']).parts[:depth]) if placed else ''
		out['files'] = files
		return out
