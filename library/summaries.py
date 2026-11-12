"""Finished album summaries, remembered in SQLite (ADR 0067).

Reading the tags of a whole library takes minutes on a network share, so the summary of an album is kept together
with the signature it was computed from (its files, their mtimes and sizes). A restart or a redeploy then costs
nothing: a stored summary whose signature still matches is used as it is.
"""

import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = 'create table if not exists summaries (path text primary key, sig text not null, summary text not null)'


class SummaryStore:
	def __init__(self, path: Path | str) -> None:
		self._lock = threading.RLock()
		self._db = sqlite3.connect(str(path), check_same_thread=False)
		self._db.execute(SCHEMA)

	def close(self) -> None:
		with self._lock:
			self._db.close()

	def get(self, path: str) -> tuple[str, dict] | None:
		with self._lock:
			row = self._db.execute(
				'select sig, summary from summaries where path = ?', (path,)
			).fetchone()
		return (row[0], json.loads(row[1])) if row else None

	def put(self, path: str, sig: str, summary: dict) -> None:
		with self._lock:
			self._db.execute(
				'insert into summaries values (?, ?, ?) on conflict(path) do update set '
				'sig = excluded.sig, summary = excluded.summary',
				(path, sig, json.dumps(summary, ensure_ascii=False)),
			)
			self._db.commit()

	def delete(self, path: str) -> None:
		with self._lock:
			self._db.execute('delete from summaries where path = ?', (path,))
			self._db.commit()

	def keep_only(self, paths: set[str]) -> int:
		"""Forget the albums that are no longer there; returns how many rows went."""
		with self._lock:
			stored = {r[0] for r in self._db.execute('select path from summaries')}
			gone = stored - paths
			self._db.executemany('delete from summaries where path = ?', [(p,) for p in gone])
			self._db.commit()
		return len(gone)
