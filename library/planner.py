"""Deciding what has to move: files in, a plan out (ADR 0037). Pure: nothing here touches the disk.

The rules are those of the discogs `bliss.py` that the library layout comes from:
- a multi-disc album (a file with DISCNUMBER above 1, a disc total above 1, or an album folder that already
  has `Disc N` folders) gets the template's disc folder for all its files;
- two folder spellings that differ only in case or Unicode form are the same folder: the first one wins and
  files that want another spelling are skipped, so the tags have to be fixed;
- a file is never moved onto an existing name; two files that want the same name: the first wins;
- a file with an empty tag the template needs is "unplaced" and stays where it is (ADR 0010: no placeholders).
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from library.template import MissingTag, Target, Template, target
from pipeline.layout import is_disc_dir


@dataclass(frozen=True)
class Item:
	"""A file as the index knows it: its path relative to the library root and its tags (first values)."""

	path: PurePosixPath
	tags: dict[str, str]


@dataclass(frozen=True)
class Move:
	src: PurePosixPath
	dst: PurePosixPath
	case_only: (
		bool  # the names differ only in case or Unicode form: needs the temporary-name rename
	)


@dataclass(frozen=True)
class Problem:
	path: PurePosixPath
	reason: str


@dataclass
class Plan:
	moves: list[Move] = field(default_factory=list)
	unplaced: list[Problem] = field(default_factory=list)  # empty tags: waiting for the user
	skipped: list[Problem] = field(
		default_factory=list
	)  # conflicts: waiting for the tags to be fixed
	in_place: int = 0


def nfd(text: str) -> str:
	return unicodedata.normalize('NFD', text)


def fold(parts: Iterable[str]) -> tuple[str, ...]:
	"""A folder's identity: case-folded and Unicode-normalised components."""
	return tuple(nfd(p).lower() for p in parts)


def leading_int(value: str, default: int = 0) -> int:
	m = re.match(r'\s*(\d+)', value or '')
	return int(m.group(1)) if m else default


def is_multi_disc(tags: dict[str, str]) -> bool:
	"""DISCNUMBER above 1, or a total above 1 (`1/2`, DISCTOTAL, TOTALDISCS)."""
	disc = tags.get('DISCNUMBER', '')
	total = max(
		leading_int(disc.split('/')[1] if '/' in disc else ''),
		leading_int(tags.get('DISCTOTAL', '')),
		leading_int(tags.get('TOTALDISCS', '')),
	)
	return leading_int(disc, 1) > 1 or total > 1


def destination(t: Target, multi: bool) -> PurePosixPath:
	parts = [*t.album_dir, *([t.disc_dir] if multi and t.disc_dir else []), t.filename]
	return PurePosixPath(*parts)


def plan(
	items: Iterable[Item],
	template: Template,
	has_disc_dirs: Callable[[tuple[str, ...]], bool] = lambda album_dir: False,
) -> Plan:
	"""The moves that bring every file to its place. `has_disc_dirs(album_dir)` says whether the album folder
	already holds `Disc N` folders (a later single-disc file then joins the multi-disc layout)."""
	result = Plan()
	placed: list[tuple[Item, Target]] = []
	for item in sorted(items, key=lambda i: str(i.path)):
		try:
			placed.append((item, target(template, item.tags)))
		except MissingTag as e:
			result.unplaced.append(Problem(item.path, f'{e.tag} is empty'))
		except ValueError as e:
			result.unplaced.append(Problem(item.path, str(e)))

	spelling: dict[tuple[str, ...], tuple[str, ...]] = {}
	multi: set[tuple[str, ...]] = set()
	for _item, t in placed:
		key = fold(t.album_dir)
		spelling.setdefault(key, t.album_dir)
	for item, t in placed:
		key = fold(t.album_dir)
		if key in multi:
			continue
		if is_multi_disc(item.tags) or has_disc_dirs(spelling[key]):
			multi.add(key)

	taken: dict[
		tuple[str, ...], PurePosixPath
	] = {}  # destination (folded) -> the file that claimed it
	for item, t in placed:
		key = fold(t.album_dir)
		if spelling[key] != t.album_dir:
			result.skipped.append(
				Problem(
					item.path,
					f'tags spell {"/".join(t.album_dir)} differently from {"/".join(spelling[key])}; fix the tags',
				)
			)
			continue
		dst = destination(t, key in multi)
		claim = fold(dst.parts)
		if claim in taken and taken[claim] != item.path:
			result.skipped.append(Problem(item.path, f'{dst} is wanted by {taken[claim]} as well'))
			continue
		taken[claim] = item.path
		if nfd(str(item.path)) == nfd(str(dst)):
			result.in_place += 1
		else:
			result.moves.append(Move(item.path, dst, case_only=fold(item.path.parts) == claim))
	return result


def album_dirs_with_discs(paths: Iterable[PurePosixPath]) -> set[tuple[str, ...]]:
	"""The folders (as tuples) that contain a `Disc N` folder, from a list of file paths."""
	out: set[tuple[str, ...]] = set()
	for p in paths:
		parent = p.parent
		if is_disc_dir(parent.name):
			out.add(parent.parent.parts)
	return out
