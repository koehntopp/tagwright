"""Moving the files (ADR 0037). Safety rules, from the discogs bliss.py:

- a file is never moved onto an existing name, and nothing is overwritten or merged;
- a name that differs only in case (or Unicode form) is changed through a temporary name, because a
  case-insensitive share sees both spellings as one file;
- an existing folder whose name differs only in case is renamed in place instead of creating a second one;
- when all FLACs of a folder go to one place, the other files in it (cover.jpg, .m3u, .cue, ...) go along;
- a folder that is empty afterwards is removed; it is never the library root, and nothing else is deleted
  except macOS and Windows litter (`.DS_Store`, `._*`, `Thumbs.db`) in a folder that would be empty otherwise.
"""

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from library.planner import Move, Problem, nfd
from library.scanner import is_music

log = logging.getLogger(__name__)

LITTER = ('.DS_Store', 'Thumbs.db', 'desktop.ini')


def is_litter(name: str) -> bool:
	return name in LITTER or name.startswith('._')


@dataclass
class Result:
	done: list[tuple[str, str]] = field(
		default_factory=list
	)  # (old, new) relative paths of moved files
	sidecars: int = 0
	errors: list[Problem] = field(default_factory=list)
	touched: set[str] = field(default_factory=set)  # directories whose content changed (relative)
	renamed_dirs: set[str] = field(
		default_factory=set
	)  # old relative paths of folders renamed in place
	removed_dirs: int = 0
	actions: list[str] = field(
		default_factory=list
	)  # one line per album-level step, for the activity log


class Executor:
	def __init__(self, root: Path, should_stop: Callable[[], bool] = lambda: False) -> None:
		self.root = root
		self.should_stop = should_stop
		self.renamed: dict[
			str, str
		] = {}  # old absolute folder -> new, so later files still under the old name are found
		self.result = Result()

	def rel(self, p: str | Path) -> str:
		return str(PurePosixPath(os.path.relpath(p, self.root)))

	def follow(self, path: str) -> str:
		for old, new in self.renamed.items():
			if path == old or path.startswith(old + os.sep):
				return new + path[len(old) :]
		return path

	def rename_case(self, parent: str, wanted: str) -> bool:
		"""Rename the entry of parent that equals `wanted` except for case to exactly `wanted`."""
		if not os.path.isdir(parent):
			return False
		names = os.listdir(parent)
		if any(nfd(n) == nfd(wanted) for n in names):
			return False
		for name in names:
			if nfd(name).lower() == nfd(wanted).lower():
				src, tmp, dst = (
					os.path.join(parent, name),
					os.path.join(parent, name + '.library-tmp'),
					os.path.join(parent, wanted),
				)
				os.rename(src, tmp)
				os.rename(tmp, dst)
				log.warning('Renamed %s -> %s (case differs from the tags)', src, wanted)
				self.result.renamed_dirs.add(self.rel(src))
				self.result.touched.add(self.rel(parent) if parent != str(self.root) else '')
				if os.path.isdir(dst):
					self.renamed[src] = dst
				return True
		return False

	def move_one(self, move: Move) -> bool:
		src = self.follow(str(self.root / move.src))
		if not os.path.isfile(src):
			return False  # vanished since the scan
		dst = self.root / move.dst
		parent = str(self.root)
		for comp in move.dst.parent.parts:
			self.rename_case(parent, comp)
			parent = os.path.join(parent, comp)
		src = self.follow(src)
		os.makedirs(dst.parent, exist_ok=True)
		if nfd(src) == nfd(str(dst)):
			return src != str(dst)  # the folder rename already did it
		if (
			nfd(os.path.dirname(src)) == nfd(str(dst.parent))
			and nfd(os.path.basename(src)).lower() == nfd(dst.name).lower()
		):
			tmp = src + '.library-tmp'
			os.rename(src, tmp)
			os.rename(tmp, dst)
			return True
		if dst.exists():
			self.result.errors.append(
				Problem(move.src, f'{move.dst} already exists; nothing is overwritten')
			)
			return False
		shutil.move(src, dst)
		return True

	def run(self, moves: list[Move]) -> Result:
		sources: dict[
			str, list[tuple[str, str]]
		] = {}  # source folder -> [(old, new)] of its moved FLACs
		for move in moves:
			if self.should_stop():
				break
			old_dir = str(move.src.parent) if str(move.src.parent) != '.' else ''
			try:
				if self.move_one(move):
					self.result.done.append((str(move.src), str(move.dst)))
					sources.setdefault(old_dir, []).append((str(move.src), str(move.dst)))
					new_dir = str(move.dst.parent)
					self.result.touched.update({old_dir, new_dir})
			except OSError as e:
				log.error('Could not move %s -> %s: %s', move.src, move.dst, e)
				self.result.errors.append(Problem(move.src, str(e)))
		for old_dir, pairs in sources.items():
			self.move_sidecars(old_dir, pairs)
		for old_dir in sorted(sources, key=lambda d: -d.count('/')):
			self.prune(old_dir)
		albums = sorted({str(PurePosixPath(new).parent) for _, new in self.result.done})
		self.result.actions = [
			f'moved {sum(1 for _, n in self.result.done if str(PurePosixPath(n).parent) == a)} file(s) to {a}'
			for a in albums
		]
		return self.result

	def move_sidecars(self, old_dir: str, pairs: list[tuple[str, str]]) -> None:
		"""Take the non-music files of a folder along when all its FLACs went to one folder."""
		absdir = self.root / old_dir if old_dir else self.root
		new_dirs = {str(PurePosixPath(new).parent) for _, new in pairs}
		if len(new_dirs) != 1 or not absdir.is_dir():
			return
		try:
			entries = list(os.scandir(absdir))
		except OSError:
			return
		if any(e.is_file() and is_music(e.name) for e in entries) or any(
			e.is_dir(follow_symlinks=False) for e in entries
		):
			return  # FLACs stay behind, or there are subfolders: the folder is not just emptied
		target = self.root / new_dirs.pop()
		for e in entries:
			if not e.is_file() or is_litter(e.name):
				continue
			dst = target / e.name
			if dst.exists():
				log.warning('Left %s in %s: %s already exists', e.name, old_dir or '/', dst)
				continue
			try:
				shutil.move(e.path, dst)
				self.result.sidecars += 1
			except OSError as err:
				log.warning('Could not move %s: %s', e.path, err)

	def prune(self, directory: str) -> None:
		"""Remove a folder that is empty (litter aside), then its parents the same way, never the root."""
		path = self.root / directory if directory else self.root
		while path != self.root and path.is_dir() and self.root in path.parents:
			try:
				names = os.listdir(path)
			except OSError:
				return
			if any(not is_litter(n) for n in names):
				return
			try:
				for n in names:
					(path / n).unlink()
				path.rmdir()
			except OSError as e:
				log.info('Folder %s stays: %s', path, e)
				return
			self.result.removed_dirs += 1
			self.result.touched.add(self.rel(path))
			path = path.parent
