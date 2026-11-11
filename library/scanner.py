"""Finding what changed on disk with as few calls as possible (ADR 0037).

A quick pass stats every known directory and lists only those whose mtime changed (on SMB and NFS there are no
change events, but a directory's mtime moves when entries are added, removed or renamed). It cannot see a tag
edited inside a file, because that changes only the file's mtime; a full pass lists everything and stats every file.
"""

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from mutagen import MutagenError
from mutagen.flac import FLAC

from library.index import Index
from library.template import INDEXED_TAGS

log = logging.getLogger(__name__)

type Reader = Callable[
	[Path], tuple[dict[str, str], str]
]  # file -> (indexed tags, error message or '')


@dataclass
class Stats:
	listed: int = 0  # directories listed
	skipped: int = 0  # directories whose mtime had not changed
	read: int = 0  # files whose tags were read
	removed: int = 0  # files that are gone
	interrupted: bool = False


def read_tags(path: Path) -> tuple[dict[str, str], str]:
	"""The tags the library needs (first values, upper-case keys); an error message instead if the file is unreadable."""
	try:
		audio = FLAC(path)
	except (MutagenError, OSError) as e:
		return {}, str(e) or type(e).__name__
	found = {k.upper(): str(v[0]) for k, v in (audio.tags or {}).items() if v}
	return {k: found[k] for k in INDEXED_TAGS if k in found}, ''


def is_music(name: str) -> bool:
	return name.lower().endswith('.flac') and not name.startswith('._')


def scan(
	root: Path,
	index: Index,
	now: float,
	full: bool = False,
	reader: Reader = read_tags,
	workers: int = 8,
	should_stop: Callable[[], bool] = lambda: False,
	progress: Callable[[str], None] | None = None,
) -> Stats:
	"""Bring the index in line with the disk. Unchanged directories are not listed unless `full`."""
	stats = Stats()
	todo: list[tuple[str, int, int]] = []  # (relative path, mtime_ns, size) of files to read
	stack = ['']
	while stack:
		if should_stop():
			stats.interrupted = True
			return stats
		rel = stack.pop()
		absdir = root / rel if rel else root
		try:
			mtime = absdir.stat().st_mtime_ns
		except OSError:
			index.delete_tree(rel)  # the directory is gone
			continue
		if not full and index.dir_mtime(rel) == mtime:
			stats.skipped += 1
			stack.extend(index.child_dirs(rel))
			continue
		stats.listed += 1
		if progress:
			progress(f'listing {rel or "/"}')
		subdirs, files = [], {}
		try:
			with os.scandir(absdir) as it:
				for entry in it:
					if entry.name.startswith('.'):
						continue
					if entry.is_dir(follow_symlinks=False):
						subdirs.append(entry.name)
					elif entry.is_file(follow_symlinks=False) and is_music(entry.name):
						st = entry.stat()
						files[entry.name] = (st.st_mtime_ns, st.st_size)
		except OSError as e:
			log.warning('Could not list %s: %s', absdir, e)
			continue
		known = index.files_in(rel)
		for name in set(known) - set(files):
			index.delete_file(f'{rel}/{name}' if rel else name)
			stats.removed += 1
		known_dirs = {d.rsplit('/', 1)[-1] for d in index.child_dirs(rel)}
		for name in known_dirs - set(subdirs):
			stats.removed += index.delete_tree(f'{rel}/{name}' if rel else name)
		for name, (m, s) in files.items():
			row = known.get(name)
			if row is None or (row.mtime_ns, row.size) != (m, s):
				todo.append((f'{rel}/{name}' if rel else name, m, s))
		index.set_dir(
			rel, mtime
		)  # the mtime from before the listing: a change during it shows up next time
		stack.extend(f'{rel}/{d}' if rel else d for d in sorted(subdirs))

	if todo:
		if progress:
			progress(f'reading tags of {len(todo)} files')
		with ThreadPoolExecutor(max_workers=workers) as pool:
			for (rel, m, s), (tags, error) in zip(
				todo, pool.map(lambda t: reader(root / t[0]), todo), strict=True
			):
				index.upsert_file(rel, m, s, tags, error, now)
				stats.read += 1
	return stats
