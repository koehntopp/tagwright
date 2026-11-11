"""Index, scanner, executor and watcher on real temporary folders with synthetic FLACs (ADR 0037)."""

import os
import threading
import time
from pathlib import Path, PurePosixPath

import pytest
from mutagen.flac import FLAC

from library import planner
from library.executor import Executor
from library.index import Index
from library.planner import Move
from library.scanner import scan
from library.template import Chip, Template, default
from library.watcher import Library, Settings

from .conftest import MakeFlac


def song(make_flac: MakeFlac, path: Path, n: int = 1, **tags: str) -> Path:
	base = {
		'ALBUMARTIST': 'Artist',
		'ALBUM': 'Album',
		'TITLE': f'Song {n}',
		'TRACKNUMBER': str(n),
		'DISCNUMBER': '1',
	}
	return make_flac(path, **{**base, **tags})


@pytest.fixture
def lib_root(tmp_path: Path) -> Path:
	root = tmp_path / 'library'
	root.mkdir()
	return root


@pytest.fixture
def index() -> Index:
	return Index(':memory:')


class TestIndex:
	def test_counts_fold_disc_folders_and_count_distinct_artists_case_insensitively(
		self, index: Index
	) -> None:
		for path, artist in (
			('A/Al/Disc 1/a.flac', 'A'),
			('A/Al/Disc 2/b.flac', 'a'),
			('B/Bl/c.flac', 'B'),
			('B/Bl/d.flac', ''),
		):
			index.upsert_file(path, 1, 1, {'ALBUMARTIST': artist}, '', 0)
		assert index.counts() == (2, 2, 4)

	def test_delete_tree_takes_files_and_subdirs_but_not_look_alikes(self, index: Index) -> None:
		for d in ('a', 'a/b', 'a_b', 'a%'):
			index.set_dir(d, 1)
		for p in ('a/x.flac', 'a/b/y.flac', 'a_b/z.flac', 'a%/w.flac'):
			index.upsert_file(p, 1, 1, {}, '', 0)
		assert index.delete_tree('a') == 2
		assert {str(i.path) for i in index.items()} == {'a_b/z.flac', 'a%/w.flac'}
		assert sorted(index.child_dirs('')) == ['a%', 'a_b']
		assert index.dir_mtime('a_b') == 1
		assert index.dir_mtime('a/b') is None

	def test_move_file_keeps_tags_and_changed_at(self, index: Index) -> None:
		index.upsert_file('x.flac', 5, 6, {'TITLE': 'T'}, '', 99.0)
		index.move_file('x.flac', 'A/y.flac')
		assert [(str(i.path), i.tags) for i in index.items()] == [('A/y.flac', {'TITLE': 'T'})]
		assert index.changed_at() == {'A/y.flac': 99.0}


class TestScanner:
	def test_the_first_scan_reads_everything_and_a_quiet_one_lists_nothing(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		song(make_flac, lib_root / 'A' / 'Al' / '01.flac')
		song(make_flac, lib_root / 'A' / 'Al' / '02.flac', 2)
		first = scan(lib_root, index, 10.0)
		assert (first.listed, first.read) == (3, 2)
		again = scan(lib_root, index, 20.0)
		assert (again.listed, again.read, again.skipped) == (0, 0, 3)
		assert {str(i.path) for i in index.items()} == {'A/Al/01.flac', 'A/Al/02.flac'}
		assert index.items()[0].tags['TITLE'] == 'Song 1'

	def test_a_new_file_lists_only_its_directory(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		song(make_flac, lib_root / 'A' / 'Al' / '01.flac')
		song(make_flac, lib_root / 'B' / 'Bl' / '01.flac')
		scan(lib_root, index, 10.0)
		song(make_flac, lib_root / 'A' / 'Al' / '02.flac', 2)
		s = scan(lib_root, index, 20.0)
		assert (s.listed, s.read) == (1, 1)

	def test_a_tag_edited_in_place_needs_a_full_pass(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		f = song(make_flac, lib_root / 'A' / '01.flac')
		scan(lib_root, index, 10.0)
		audio = FLAC(f)
		audio['TITLE'] = ['Changed']
		audio.save()
		os.utime(
			f, (f.stat().st_atime, f.stat().st_mtime + 5)
		)  # coarse timestamps must not hide the edit
		assert scan(lib_root, index, 20.0).read == 0  # the directory did not change
		assert scan(lib_root, index, 30.0, full=True).read == 1
		assert index.items()[0].tags['TITLE'] == 'Changed'

	def test_removed_files_and_folders_leave_the_index(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		a = song(make_flac, lib_root / 'A' / 'Al' / '01.flac')
		song(make_flac, lib_root / 'A' / 'Al' / '02.flac', 2)
		song(make_flac, lib_root / 'B' / '01.flac')
		scan(lib_root, index, 10.0)
		a.unlink()
		assert scan(lib_root, index, 20.0).removed == 1
		import shutil

		shutil.rmtree(lib_root / 'B')
		scan(lib_root, index, 30.0)
		assert {str(i.path) for i in index.items()} == {'A/Al/02.flac'}

	def test_other_files_hidden_names_and_apple_double_files_are_ignored(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		song(make_flac, lib_root / 'A' / '01.flac')
		(lib_root / 'A' / 'cover.jpg').write_bytes(b'x')
		(lib_root / 'A' / '._01.flac').write_bytes(b'x')
		(lib_root / '.hidden').mkdir()
		song(make_flac, lib_root / '.hidden' / '01.flac')
		scan(lib_root, index, 1.0)
		assert [str(i.path) for i in index.items()] == ['A/01.flac']

	def test_an_unreadable_file_is_recorded_with_its_error(
		self, lib_root: Path, index: Index
	) -> None:
		(lib_root / 'bad.flac').write_bytes(b'not flac')
		scan(lib_root, index, 1.0)
		assert 'bad.flac' in index.errors()

	def test_a_stop_request_ends_the_scan(
		self, make_flac: MakeFlac, lib_root: Path, index: Index
	) -> None:
		song(make_flac, lib_root / 'A' / '01.flac')
		assert scan(lib_root, index, 1.0, should_stop=lambda: True).interrupted


class TestExecutor:
	def move(self, root: Path, src: str, dst: str, case_only: bool = False) -> Move:
		return Move(PurePosixPath(src), PurePosixPath(dst), case_only)

	def test_moves_a_file_and_creates_folders(self, make_flac: MakeFlac, lib_root: Path) -> None:
		song(make_flac, lib_root / 'x.flac')
		r = Executor(lib_root).run([self.move(lib_root, 'x.flac', 'A/Al/01_01_T.flac')])
		assert (lib_root / 'A' / 'Al' / '01_01_T.flac').is_file()
		assert not (lib_root / 'x.flac').exists()
		assert r.done == [('x.flac', 'A/Al/01_01_T.flac')]
		assert r.actions == ['moved 1 file(s) to A/Al']

	def test_never_overwrites(self, make_flac: MakeFlac, lib_root: Path) -> None:
		song(make_flac, lib_root / 'x.flac')
		song(make_flac, lib_root / 'A' / 'y.flac', 9)
		r = Executor(lib_root).run([self.move(lib_root, 'x.flac', 'A/y.flac')])
		assert (lib_root / 'x.flac').is_file()
		assert FLAC(lib_root / 'A' / 'y.flac')['TITLE'] == ['Song 9']
		assert 'already exists' in r.errors[0].reason

	def test_a_case_only_file_rename_goes_through_a_temporary_name(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'A' / '01_01_song.flac')
		Executor(lib_root).run(
			[self.move(lib_root, 'A/01_01_song.flac', 'A/01_01_Song.flac', True)]
		)
		assert sorted(os.listdir(lib_root / 'A')) == ['01_01_Song.flac']

	def test_a_folder_that_differs_only_in_case_is_renamed_not_duplicated(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'chris_de_burgh' / 'Al' / '01.flac')
		song(make_flac, lib_root / 'chris_de_burgh' / 'Al' / '02.flac', 2)
		moves = [
			self.move(lib_root, 'chris_de_burgh/Al/01.flac', 'Chris_De_Burgh/Al/01.flac', True),
			self.move(lib_root, 'chris_de_burgh/Al/02.flac', 'Chris_De_Burgh/Al/02.flac', True),
		]
		r = Executor(lib_root).run(moves)
		assert sorted(os.listdir(lib_root)) == ['Chris_De_Burgh']
		assert sorted(os.listdir(lib_root / 'Chris_De_Burgh' / 'Al')) == ['01.flac', '02.flac']
		assert 'chris_de_burgh' in r.renamed_dirs
		assert not r.errors

	def test_sidecars_travel_when_all_flacs_go_to_one_folder(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'dump' / '01.flac')
		(lib_root / 'dump' / 'cover.jpg').write_bytes(b'img')
		(lib_root / 'dump' / '.DS_Store').write_bytes(b'junk')
		r = Executor(lib_root).run([self.move(lib_root, 'dump/01.flac', 'A/Al/01.flac')])
		assert sorted(os.listdir(lib_root / 'A' / 'Al')) == ['01.flac', 'cover.jpg']
		assert not (lib_root / 'dump').exists()  # emptied, litter and all
		assert (r.sidecars, r.removed_dirs) == (1, 1)

	def test_sidecars_stay_when_flacs_remain_or_go_to_different_folders(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'mix' / '01.flac')
		song(make_flac, lib_root / 'mix' / '02.flac', 2)
		(lib_root / 'mix' / 'cover.jpg').write_bytes(b'img')
		Executor(lib_root).run(
			[
				self.move(lib_root, 'mix/01.flac', 'A/01.flac'),
				self.move(lib_root, 'mix/02.flac', 'B/02.flac'),
			]
		)
		assert (lib_root / 'mix' / 'cover.jpg').is_file()
		song(make_flac, lib_root / 'part' / '01.flac')
		song(make_flac, lib_root / 'part' / '02.flac', 2)
		(lib_root / 'part' / 'cover.jpg').write_bytes(b'img')
		Executor(lib_root).run([self.move(lib_root, 'part/01.flac', 'C/01.flac')])
		assert (lib_root / 'part' / 'cover.jpg').is_file()

	def test_a_sidecar_that_would_overwrite_stays(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'dump' / '01.flac')
		(lib_root / 'dump' / 'cover.jpg').write_bytes(b'new')
		(lib_root / 'A').mkdir()
		(lib_root / 'A' / 'cover.jpg').write_bytes(b'old')
		Executor(lib_root).run([self.move(lib_root, 'dump/01.flac', 'A/01.flac')])
		assert (lib_root / 'A' / 'cover.jpg').read_bytes() == b'old'
		assert (lib_root / 'dump' / 'cover.jpg').read_bytes() == b'new'

	def test_emptied_folders_are_removed_up_to_but_not_including_the_root(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'a' / 'b' / 'c' / '01.flac')
		song(make_flac, lib_root / 'a' / 'keep.flac', 2)
		Executor(lib_root).run([self.move(lib_root, 'a/b/c/01.flac', 'X/01.flac')])
		assert not (lib_root / 'a' / 'b').exists()
		assert (lib_root / 'a' / 'keep.flac').is_file()
		song(make_flac, lib_root / 'only' / '01.flac')
		Executor(lib_root).run([self.move(lib_root, 'only/01.flac', '01.flac')])
		assert lib_root.is_dir()

	def test_a_vanished_file_is_skipped_and_stop_ends_the_run(
		self, make_flac: MakeFlac, lib_root: Path
	) -> None:
		song(make_flac, lib_root / 'x.flac')
		assert Executor(lib_root).run([self.move(lib_root, 'gone.flac', 'A/gone.flac')]).done == []
		assert (
			Executor(lib_root, lambda: True).run([self.move(lib_root, 'x.flac', 'A/x.flac')]).done
			== []
		)
		assert (lib_root / 'x.flac').is_file()


class Clock:
	"""A clock that starts at the real time (file mtimes are real) and moves only when told."""

	def __init__(self) -> None:
		self.now = time.time()

	def __call__(self) -> float:
		return self.now


def library(root: Path, tmp_path: Path, clock: Clock, **kw: float | bool) -> Library:
	settings = Settings(**kw)
	return Library(lambda: root, tmp_path / 'library.db', lambda: settings, clock=clock)


class TestWatcher:
	def messy(self, make_flac: MakeFlac, root: Path) -> None:
		song(make_flac, root / 'dump' / 'a.flac', 1, VERSION='2020 CD')
		song(make_flac, root / 'dump' / 'b.flac', 2, VERSION='2020 CD')

	def test_files_wait_for_the_cooldown_then_move(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=60)
		lib.cycle()
		s = lib.status()
		assert (s['phase'], s['waiting']) == ('waiting', 2)
		assert (lib_root / 'dump' / 'a.flac').is_file()
		clock.now += 90
		lib.cycle()
		assert sorted(p.name for p in (lib_root / 'Artist' / 'Album_2020_CD').iterdir()) == [
			'01_01_Song_1.flac',
			'01_02_Song_2.flac',
		]
		assert not (lib_root / 'dump').exists()
		s = lib.status()
		assert s['phase'] == 'idle'
		assert (s['artists'], s['albums'], s['tracks']) == (1, 1, 2)
		texts = [r['text'] for r in s['recent']]
		assert 'moved 2 file(s) to Artist/Album_2020_CD' in texts
		assert 'removed 1 empty folder(s)' in texts

	def test_a_file_that_keeps_changing_keeps_its_album_waiting(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=60)
		lib.cycle()
		clock.now += 90
		song(make_flac, lib_root / 'dump' / 'c.flac', 3, VERSION='2020 CD')  # a third track arrives
		lib.cycle()
		assert (lib_root / 'dump' / 'a.flac').is_file()  # the album is not settled again yet
		assert lib.status()['waiting'] == 3
		clock.now += 90
		lib.cycle()
		assert len(list((lib_root / 'Artist' / 'Album_2020_CD').iterdir())) == 3

	def test_report_only_changes_nothing_and_lists_the_plan(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, apply=False, cooldown=0)
		clock.now += 5
		lib.cycle()
		assert (lib_root / 'dump' / 'a.flac').is_file()
		assert lib.status()['planned'] == [
			{'from': 'dump/a.flac', 'to': 'Artist/Album_2020_CD/01_01_Song_1.flac'},
			{'from': 'dump/b.flac', 'to': 'Artist/Album_2020_CD/01_02_Song_2.flac'},
		]

	def test_unplaced_and_unreadable_files_stay_and_are_listed(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		song(make_flac, lib_root / 'no_title.flac', TITLE='')
		(lib_root / 'bad.flac').write_bytes(b'junk')
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=0)
		clock.now += 5
		lib.cycle()
		reasons = {u['path']: u['reason'] for u in lib.status()['unplaced']}
		assert reasons['no_title.flac'] == 'TITLE is empty'
		assert reasons['bad.flac'].startswith('unreadable')
		assert (lib_root / 'no_title.flac').is_file()

	def test_a_library_that_is_in_order_is_left_alone(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		song(make_flac, lib_root / 'Artist' / 'Album' / '01_01_Song_1.flac')
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=0)
		clock.now += 5
		before = (lib_root / 'Artist' / 'Album' / '01_01_Song_1.flac').stat().st_mtime_ns
		lib.cycle()
		assert lib.status()['recent'] == []
		assert (lib_root / 'Artist' / 'Album' / '01_01_Song_1.flac').stat().st_mtime_ns == before

	def test_a_tag_fix_moves_the_file_after_a_full_pass(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		f = song(make_flac, lib_root / 'Artist' / 'Album' / '01_01_Song_1.flac')
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=10)
		clock.now += 30
		lib.cycle()
		audio = FLAC(f)
		audio['TITLE'] = ['Better Title']
		audio.save()
		os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 2))
		clock.now += 30
		lib.cycle()  # quick: the folder did not change, so nothing is noticed
		assert f.is_file()
		lib.rescan()
		lib.cycle(full=True)
		clock.now += 30
		lib.cycle()
		assert (lib_root / 'Artist' / 'Album' / '01_01_Better_Title.flac').is_file()

	def test_a_changed_template_re_lays_out_the_library(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		song(make_flac, lib_root / 'Artist' / 'Album' / '01_01_Song_1.flac')
		clock = Clock()
		settings = [Settings(cooldown=0)]
		lib = Library(lambda: lib_root, tmp_path / 'library.db', lambda: settings[0], clock=clock)
		clock.now += 5
		lib.cycle()
		settings[0] = Settings(
			cooldown=0,
			template=Template(
				folders=((Chip('ALBUM'),),),
				filename=(Chip('TRACKNUMBER', fmt='num', pad=2), Chip(text='_'), Chip('TITLE')),
				disc_folder=None,
			),
		)
		clock.now += 5
		lib.cycle(full=True)
		assert (lib_root / 'Album' / '01_Song_1.flac').is_file()
		assert not (lib_root / 'Artist').exists()

	def test_errors_are_reported_in_the_status(self, lib_root: Path, tmp_path: Path) -> None:
		bad = Library(lambda: None, tmp_path / 'a.db', lambda: Settings())
		bad.cycle()
		assert bad.status()['phase'] == 'error'
		broken = Library(
			lambda: lib_root,
			tmp_path / 'b.db',
			lambda: Settings(template=Template(folders=(), filename=())),
		)
		broken.cycle()
		assert 'invalid' in broken.status()['error']

	def test_the_exclusive_lock_keeps_moves_apart_from_other_writers(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, cooldown=0)
		clock.now += 5
		done = threading.Event()
		with lib.exclusive:
			t = threading.Thread(target=lambda: (lib.cycle(), done.set()))
			t.start()
			assert not done.wait(0.5)  # the pass waits while someone else holds the lock
			assert (lib_root / 'dump' / 'a.flac').is_file()
		t.join(10)
		assert done.is_set()
		assert not (lib_root / 'dump').exists()

	def test_the_thread_picks_up_new_files_and_stops(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		lib = Library(
			lambda: lib_root, tmp_path / 'library.db', lambda: Settings(cooldown=0.2, interval=0.3)
		)
		lib.start()
		try:
			time.sleep(0.5)
			self.messy(make_flac, lib_root)
			deadline = time.time() + 15
			while time.time() < deadline and (lib_root / 'dump').exists():
				lib.poke()
				time.sleep(0.3)
			assert (lib_root / 'Artist' / 'Album_2020_CD' / '01_01_Song_1.flac').is_file()
		finally:
			lib.stop()
		assert not lib._thread.is_alive()

	def test_preview_shows_what_a_template_does_to_one_album(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		clock = Clock()
		lib = library(lib_root, tmp_path, clock, apply=False)
		lib.cycle()
		p = lib.preview(default())
		assert p['album'] == 'dump'
		assert p['album_dir'] == 'Artist/Album_2020_CD'
		assert [f['name'] for f in p['files']] == ['01_01_Song_1.flac', '01_02_Song_2.flac']
		assert [(f['from'], f['to']) for f in p['files']] == [
			('dump/a.flac', 'Artist/Album_2020_CD/01_01_Song_1.flac'),
			('dump/b.flac', 'Artist/Album_2020_CD/01_02_Song_2.flac'),
		]
		assert lib.preview(Template(folders=(), filename=()))['errors']

	def test_the_preview_picks_a_folder_with_placeable_files_and_shows_disc_folders(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		song(
			make_flac, lib_root / 'a_unplaced' / 'x.flac', TITLE=''
		)  # sorts first but cannot be placed
		song(make_flac, lib_root / 'b' / '01.flac', DISCNUMBER='1')
		song(make_flac, lib_root / 'b' / '02.flac', 2, DISCNUMBER='2')
		lib = library(lib_root, tmp_path, Clock(), apply=False)
		lib.cycle()
		p = lib.preview(default())
		assert p['album'] == 'b'
		assert p['album_dir'] == 'Artist/Album'
		assert [f['name'] for f in p['files']] == [
			'Disc 1/01_01_Song_1.flac',
			'Disc 2/02_02_Song_2.flac',
		]

	def test_the_plan_agrees_with_the_planner_module(
		self, make_flac: MakeFlac, lib_root: Path, tmp_path: Path
	) -> None:
		self.messy(make_flac, lib_root)
		idx = Index(':memory:')
		scan(lib_root, idx, 1.0)
		assert len(planner.plan(idx.items(), default()).moves) == 2
