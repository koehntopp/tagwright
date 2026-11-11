"""What is on disk, remembered in SQLite, so that a pass over a settled library only stats directories (ADR 0037).

Paths are POSIX strings relative to the library root; the root itself is ''. A directory's mtime changes when a
file or folder in it is added, removed or renamed, so an unchanged directory needs no listing. A file's
(mtime, size) says whether its tags have to be read again. `changed_at` is when this process first saw the file in
its present state; the cooldown counts from it.
"""

import json
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from library.planner import Item
from pipeline.layout import is_disc_dir

SCHEMA = """
create table if not exists dirs (path text primary key, parent text not null, mtime_ns integer not null);
create table if not exists files (
	path text primary key, dir text not null, name text not null,
	mtime_ns integer not null, size integer not null, tags text not null, error text not null default '',
	changed_at real not null
);
create index if not exists files_dir on files (dir);
create index if not exists dirs_parent on dirs (parent);
"""


@dataclass(frozen=True)
class Row:
	mtime_ns: int
	size: int
	changed_at: float


def parent_of(path: str) -> str:
	return str(PurePosixPath(path).parent) if '/' in path else ''


class Index:
	def __init__(self, path: Path | str) -> None:
		self._lock = threading.RLock()
		self._db = sqlite3.connect(str(path), check_same_thread=False)
		self._db.executescript(SCHEMA)

	def close(self) -> None:
		with self._lock:
			self._db.close()

	def clear(self) -> None:
		with self._lock:
			self._db.executescript('delete from files; delete from dirs;')
			self._db.commit()

	# --- directories
	def dir_mtime(self, path: str) -> int | None:
		with self._lock:
			row = self._db.execute('select mtime_ns from dirs where path = ?', (path,)).fetchone()
		return row[0] if row else None

	def set_dir(self, path: str, mtime_ns: int) -> None:
		with self._lock:
			self._db.execute(
				'insert into dirs values (?, ?, ?) on conflict(path) do update set mtime_ns = excluded.mtime_ns',
				(path, parent_of(path) if path else '', mtime_ns),
			)
			self._db.commit()

	def child_dirs(self, path: str) -> list[str]:
		with self._lock:
			rows = self._db.execute(
				'select path from dirs where parent = ? and path != ?', (path, '')
			).fetchall()
		return [r[0] for r in rows]

	def forget_dirs(self, paths: Iterable[str]) -> None:
		"""Make the next pass list these directories again: their mtime becomes unknown. (The rows stay, because the
		scanner finds subdirectories through them.)"""
		with self._lock:
			self._db.executemany(
				'update dirs set mtime_ns = -1 where path = ?', [(p,) for p in paths]
			)
			self._db.commit()

	def forget_tree(self, path: str) -> None:
		"""Make the next pass list this directory and everything below it again."""
		like = path.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '/%'
		with self._lock:
			self._db.execute(
				"update dirs set mtime_ns = -1 where path = ? or path like ? escape '\\'",
				(path, like),
			)
			self._db.commit()

	def delete_tree(self, path: str) -> int:
		"""Drop a directory, its subdirectories and all their files; returns the number of files dropped."""
		like = path.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '/%'
		with self._lock:
			n = self._db.execute(
				"delete from files where dir = ? or path like ? escape '\\'", (path, like)
			).rowcount
			self._db.execute(
				"delete from dirs where path = ? or path like ? escape '\\'", (path, like)
			)
			self._db.commit()
		return n

	# --- files
	def files_in(self, directory: str) -> dict[str, Row]:
		with self._lock:
			rows = self._db.execute(
				'select name, mtime_ns, size, changed_at from files where dir = ?', (directory,)
			).fetchall()
		return {name: Row(m, s, c) for name, m, s, c in rows}

	def upsert_file(
		self,
		path: str,
		mtime_ns: int,
		size: int,
		tags: dict[str, str],
		error: str,
		changed_at: float,
	) -> None:
		with self._lock:
			self._db.execute(
				'insert into files values (?, ?, ?, ?, ?, ?, ?, ?) on conflict(path) do update set '
				'mtime_ns = excluded.mtime_ns, size = excluded.size, tags = excluded.tags, error = excluded.error, '
				'changed_at = excluded.changed_at',
				(
					path,
					parent_of(path),
					PurePosixPath(path).name,
					mtime_ns,
					size,
					json.dumps(tags, ensure_ascii=False),
					error,
					changed_at,
				),
			)
			self._db.commit()

	def delete_file(self, path: str) -> None:
		with self._lock:
			self._db.execute('delete from files where path = ?', (path,))
			self._db.commit()

	def move_file(self, old: str, new: str) -> None:
		"""A file the library moved itself: keep its tags and its changed_at, take the new place."""
		with self._lock:
			row = self._db.execute(
				'select mtime_ns, size, tags, error, changed_at from files where path = ?', (old,)
			).fetchone()
			self._db.execute('delete from files where path = ?', (old,))
			if row:
				self._db.execute(
					'insert or replace into files values (?, ?, ?, ?, ?, ?, ?, ?)',
					(new, parent_of(new), PurePosixPath(new).name, *row),
				)
			self._db.commit()

	def items(self) -> list[Item]:
		with self._lock:
			rows = self._db.execute('select path, tags from files order by path').fetchall()
		return [Item(PurePosixPath(p), json.loads(t)) for p, t in rows]

	def errors(self) -> dict[str, str]:
		with self._lock:
			rows = self._db.execute("select path, error from files where error != ''").fetchall()
		return dict(rows)

	def changed_at(self) -> dict[str, float]:
		with self._lock:
			rows = self._db.execute('select path, changed_at from files').fetchall()
		return dict(rows)

	def mtimes(self) -> dict[str, int]:
		with self._lock:
			rows = self._db.execute('select path, mtime_ns from files').fetchall()
		return dict(rows)

	def counts(self) -> tuple[int, int, int]:
		"""(album artists, albums, tracks). An album is a folder with FLACs, a `Disc N` folder counting as its parent."""
		with self._lock:
			rows = self._db.execute('select dir, tags from files').fetchall()
		albums, artists = set(), set()
		for directory, raw in rows:
			p = PurePosixPath(directory)
			albums.add(str(p.parent) if is_disc_dir(p.name) else directory)
			if artist := json.loads(raw).get('ALBUMARTIST', '').strip().lower():
				artists.add(artist)
		return len(artists), len(albums), len(rows)
