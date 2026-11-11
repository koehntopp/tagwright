"""The lyrics step: what happens to each track, with a fake lrclib (ADR 0006, 0021, 0036)."""

import logging
from pathlib import Path

import pytest
from mutagen.flac import FLAC

from pipeline import lyrics
from pipeline.config import Config
from pipeline.tools import Context, Stopped

from .conftest import MakeFlac

SYNCED = '[00:01.123]hello there\n[00:05.456]second line'


class Lookup:
	"""A fake lrclib: answers by track_name (a dict body, {} for 404, None for "no answer"), records the calls."""

	def __init__(
		self, answers: dict[str, dict | None] | None = None, default: dict | None = None
	) -> None:
		self.answers = answers or {}
		self.default = {} if default is None else default
		self.calls: list[dict[str, str]] = []

	def __call__(self, params: dict[str, str]) -> dict | None:
		self.calls.append(params)
		return self.answers.get(params['track_name'], self.default)


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
	return Context(Config(data_dir=tmp_path / 'data'))


def song(make_flac: MakeFlac, path: Path, **tags: str) -> Path:
	base = {
		'ALBUMARTIST': 'Artist',
		'TITLE': 'Song',
		'ALBUM': 'Album',
		'DISCOGS_RELEASE_ID': '1',
		'TRACKNUMBER': '1',
	}
	return make_flac(path, **{**base, **tags})


def lyrics_of(path: Path) -> str:
	return (FLAC(path).tags.get('LYRICS') or [''])[0]


class TestHelpers:
	@pytest.mark.parametrize(
		('title', 'stripped'),
		[
			('Song (Live at Wembley)', 'Song'),
			('Song [Remastered 2011]', 'Song'),
			('Song (a) (b)', 'Song (a)'),  # only one trailing group
			('Song', 'Song'),
			('(Intro)', ''),
			('Song (nested (x))', 'Song (nested (x))'),  # nested brackets are not stripped
		],
	)
	def test_strip_trailing_bracket(self, title: str, stripped: str) -> None:
		assert lyrics.strip_trailing_bracket(title) == stripped

	@pytest.mark.parametrize(
		('values', 'instrumental'),
		[
			(['zxx'], True),
			([' ZXX '], True),
			(['zxx', 'eng'], False),
			(['mul'], False),
			(['und'], False),
			([], False),
		],
	)
	def test_only_a_lone_zxx_is_instrumental(self, values: list[str], instrumental: bool) -> None:
		assert lyrics.is_instrumental_language(values) is instrumental

	def test_search_order(self) -> None:
		params = lyrics.search_params('Album Artist', 'Track Artist', 'Song (Live)', 'Album', '200')
		assert [(p['artist_name'], p['track_name'], 'album_name' in p) for p in params] == [
			('Album Artist', 'Song (Live)', True),
			('Album Artist', 'Song (Live)', False),
			('Album Artist', 'Song', True),
			('Album Artist', 'Song', False),
			('Track Artist', 'Song (Live)', True),
			('Track Artist', 'Song (Live)', False),
			('Track Artist', 'Song', True),
			('Track Artist', 'Song', False),
		]
		assert all(p['duration'] == '200' for p in params)

	def test_one_artist_and_one_name_when_they_do_not_differ(self) -> None:
		assert len(lyrics.search_params('A', 'A', 'Song', 'Al', '1')) == 2
		assert len(lyrics.search_params('A', '', 'Song', 'Al', '1')) == 2


class TestFetchOne:
	def test_a_missing_file_is_skipped(self, tmp_path: Path) -> None:
		r = lyrics.fetch_one(tmp_path / 'gone.flac', Lookup())
		assert (r.action, r.kind) == ('skip', 'none')

	def test_an_unreadable_file_is_an_error(
		self, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		bad = tmp_path / 'bad.flac'
		bad.write_bytes(b'nope')
		with caplog.at_level(logging.WARNING):
			assert lyrics.fetch_one(bad, Lookup()).action == 'error'
		assert 'Could not read FLAC tags' in caplog.text

	@pytest.mark.parametrize('missing', ['TITLE', 'ALBUMARTIST'])
	def test_without_artist_or_title_nothing_is_asked(
		self, missing: str, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		tags = {'ALBUMARTIST': 'A', 'TITLE': 'T'}
		del tags[missing]
		f = make_flac(tmp_path / 'a.flac', **tags)  # no ARTIST either
		lookup = Lookup()
		assert lyrics.fetch_one(f, lookup).action == 'error'
		assert lookup.calls == []

	def test_the_artist_falls_back_to_artist(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		f = make_flac(tmp_path / 'a.flac', ARTIST='Track Artist', TITLE='Song')
		lookup = Lookup({'Song': {'plainLyrics': 'words'}})
		r = lyrics.fetch_one(f, lookup)
		assert r.artist == 'Track Artist'
		assert lookup.calls[0]['artist_name'] == 'Track Artist'

	def test_a_canonical_instrumental_marker_is_left_alone(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		marker = '[la:zxx]\n[instrumental:true]\n[00:00.00](Instrumental)'
		lookup = Lookup()
		r = lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac', LYRICS=marker), lookup)
		assert (r.kind, r.action, r.lyrics) == ('instrumental', 'skip', marker)
		assert lookup.calls == []

	def test_a_hand_typed_marker_becomes_the_canonical_block_without_lrclib(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		lookup = Lookup()
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS='[00:00.00][Instrumental]'), lookup
		)
		assert (r.kind, r.action) == ('instrumental', 'fix')
		assert '[instrumental:true]' in r.lyrics
		assert r.lyrics.startswith('[ar:Artist]\n[ti:Song]\n[al:Album]\n[length:00:00]')
		assert lookup.calls == []

	@pytest.mark.parametrize('existing', ['', 'just some words'])
	def test_zxx_marks_empty_and_plain_tags_instrumental_without_a_request(
		self, existing: str, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		tags = {'LYRICS': existing} if existing else {}
		lookup = Lookup()
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS_LANGUAGE='zxx', **tags), lookup
		)
		assert (r.kind, r.action) == ('instrumental', 'new')
		assert lookup.calls == []

	def test_zxx_does_not_override_a_synced_lrc(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		lookup = Lookup()
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS_LANGUAGE='zxx', LYRICS='[00:01.00]hello'),
			lookup,
		)
		assert r.kind == 'lrc'
		assert '[instrumental:true]' not in r.lyrics
		assert lookup.calls == []

	@pytest.mark.parametrize('languages', ['eng', 'mul'])
	def test_other_languages_still_ask_lrclib(
		self, languages: str, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		lookup = Lookup()
		lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac', LYRICS_LANGUAGE=languages), lookup)
		assert lookup.calls

	def test_an_existing_lrc_is_corrected_in_place_and_never_replaced(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		lookup = Lookup({'Song': {'syncedLyrics': '[00:09.00]other source'}})
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS='[00:01.00]it’s   me'), lookup
		)
		assert (r.kind, r.action) == ('lrc', 'fix')
		assert (
			r.lyrics.splitlines()[-1] == "[00:01.00]It's   me"
		)  # typography fixed, inner spaces kept
		assert r.lyrics.startswith('[ar:Artist]')  # headers added
		assert lookup.calls == []

	def test_a_correct_lrc_is_skipped(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		first = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS='[00:01.00]hello'), Lookup()
		)
		again = lyrics.fetch_one(
			song(make_flac, tmp_path / 'b.flac', LYRICS=first.lyrics), Lookup()
		)
		assert (again.kind, again.action, again.lyrics) == ('lrc', 'skip', first.lyrics)

	def test_synced_lyrics_from_lrclib_get_headers_and_two_digit_hundredths(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac'), Lookup({'Song': {'syncedLyrics': SYNCED}})
		)
		assert (r.kind, r.action) == ('lrc', 'new')
		assert r.lyrics.splitlines()[-2:] == ['[00:01.12]Hello there', '[00:05.45]Second line']
		assert r.lyrics.startswith('[ar:Artist]\n[ti:Song]\n[al:Album]\n[length:00:00]\n')

	def test_invalid_timestamps_are_rejected_and_plain_lyrics_used(
		self, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		body = {'syncedLyrics': '[100:00:01.00]bad', 'plainLyrics': 'it’s plain'}
		with caplog.at_level(logging.WARNING):
			r = lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac'), Lookup({'Song': body}))
		assert (r.kind, r.action, r.lyrics) == ('txt', 'new', "It's plain")
		assert 'Invalid LRC timestamps' in caplog.text

	def test_plain_lyrics_are_normalized_and_capitalized(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac'),
			Lookup({'Song': {'plainLyrics': 'first…\nsecond'}}),
		)
		assert r.lyrics == 'First...\nSecond'

	def test_plain_lyrics_never_replace_existing_text(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS='mine'),
			Lookup({'Song': {'plainLyrics': 'theirs'}}),
		)
		assert (r.kind, r.action, r.lyrics) == (
			'txt',
			'fix',
			'Mine',
		)  # only capitalized, never theirs

	def test_synced_lyrics_do_replace_plain_text(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', LYRICS='Plain text'),
			Lookup({'Song': {'syncedLyrics': SYNCED}}),
		)
		assert (r.kind, r.action) == ('lrc', 'new')

	def test_an_instrumental_flag_from_lrclib_writes_the_marker(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac'), Lookup({'Song': {'instrumental': True}})
		)
		assert (r.kind, r.action) == ('instrumental', 'new')
		assert '[instrumental:true]' in r.lyrics

	def test_nothing_found_keeps_nothing(
		self, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		with caplog.at_level(logging.WARNING):
			r = lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac'), Lookup())
		assert (r.kind, r.action, r.lyrics) == ('none', 'skip', '')
		assert 'No lyrics found at lrclib' in caplog.text

	def test_nothing_found_still_cleans_existing_plain_text(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		fix = lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac', LYRICS='it’s plain'), Lookup())
		assert (fix.kind, fix.action, fix.lyrics) == ('txt', 'fix', "It's plain")
		keep = lyrics.fetch_one(
			song(make_flac, tmp_path / 'b.flac', LYRICS='Already fine'), Lookup()
		)
		assert (keep.action, keep.lyrics) == ('skip', 'Already fine')

	def test_the_first_variant_that_hits_ends_the_search(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		lookup = Lookup({'Song': {'plainLyrics': 'found'}})
		lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', TITLE='Song (Live)'), lookup
		)  # misses, then 'Song'
		assert [c['track_name'] for c in lookup.calls] == ['Song (Live)', 'Song (Live)', 'Song']
		assert 'album_name' in lookup.calls[0]
		assert 'album_name' not in lookup.calls[1]

	def test_a_stripped_title_hit_is_logged(
		self, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		with caplog.at_level(logging.INFO):
			lyrics.fetch_one(
				song(make_flac, tmp_path / 'a.flac', TITLE='Song (Live)'),
				Lookup({'Song': {'plainLyrics': 'x'}}),
			)
		assert "Lyrics found via stripped title 'Song' (original: 'Song (Live)')" in caplog.text

	def test_the_track_artist_is_tried_after_the_album_artist(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		lookup = Lookup()
		lyrics.fetch_one(
			song(
				make_flac, tmp_path / 'a.flac', ALBUMARTIST='Various Artists', ARTIST='Real Artist'
			),
			lookup,
		)
		assert [c['artist_name'] for c in lookup.calls] == ['Various Artists'] * 2 + [
			'Real Artist'
		] * 2

	def test_the_duration_is_the_rounded_length(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		lookup = Lookup()
		lyrics.fetch_one(song(make_flac, tmp_path / 'a.flac'), lookup)
		assert lookup.calls[0]['duration'] == '0'  # 0.2 s

	def test_an_unanswered_lookup_stops_the_search_and_writes_nothing(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		calls: list[dict[str, str]] = []

		def down(params: dict[str, str]) -> dict | None:
			calls.append(params)
			return None

		r = lyrics.fetch_one(
			song(make_flac, tmp_path / 'a.flac', TITLE='Song (Live)', LYRICS='keep me'), down
		)
		assert r.action == 'failed'
		assert len(calls) == 1  # no further variants are tried


class TestCollect:
	def test_only_folders_whose_first_file_has_a_numeric_release_id(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		a = tmp_path / 'a'
		song(make_flac, a / 'Disc 1' / '01.flac')
		song(make_flac, a / 'Disc 1' / '02.flac')
		make_flac(a / 'Disc 2' / '01.flac', DISCOGS_RELEASE_ID='abc')
		make_flac(a / 'Disc 3' / '01.flac')
		assert [p.relative_to(a).as_posix() for p in lyrics.collect_tracks(a)] == [
			'Disc 1/01.flac',
			'Disc 1/02.flac',
		]

	def test_a_single_folder_album(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		song(make_flac, tmp_path / 'a' / '01.flac')
		make_flac(tmp_path / 'a' / '02.flac')  # judged by the first file of the folder only
		assert len(lyrics.collect_tracks(tmp_path / 'a')) == 2

	def test_unreadable_first_file_skips_the_folder(self, tmp_path: Path) -> None:
		(tmp_path / 'a').mkdir()
		(tmp_path / 'a' / '01.flac').write_bytes(b'junk')
		assert lyrics.collect_tracks(tmp_path / 'a') == []


class TestWrite:
	def stats(self) -> dict[str, int]:
		return dict.fromkeys(('lrc', 'txt', 'none', 'instrumental', 'new', 'fixed', 'failed'), 0)

	def test_new_lyrics_are_written_and_counted(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		f = song(make_flac, tmp_path / 'a.flac')
		stats = self.stats()
		lyrics.write_lyrics(lyrics.Result(f, 'A', 'T', '[00:01.00]x', 'lrc', 'new'), stats)
		assert lyrics_of(f) == '[00:01.00]x'
		assert (stats['lrc'], stats['new'], stats['fixed']) == (1, 1, 0)
		assert FLAC(f)['TITLE'] == ['Song']  # other tags survive

	def test_a_fix_counts_as_fixed(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		f = song(make_flac, tmp_path / 'a.flac')
		stats = self.stats()
		lyrics.write_lyrics(lyrics.Result(f, 'A', 'T', 'x', 'txt', 'fix'), stats)
		assert (stats['txt'], stats['new'], stats['fixed']) == (1, 0, 1)

	@pytest.mark.parametrize('action', ['skip', 'error', 'failed'])
	def test_other_actions_write_nothing(
		self, action: str, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = song(make_flac, tmp_path / 'a.flac', LYRICS='keep')
		stats = self.stats()
		lyrics.write_lyrics(lyrics.Result(f, 'A', 'T', 'changed', 'txt', action), stats)
		assert lyrics_of(f) == 'keep'
		assert (stats['new'], stats['fixed']) == (0, 0)

	def test_kinds_are_counted(self, make_flac: MakeFlac, tmp_path: Path) -> None:
		f = song(make_flac, tmp_path / 'a.flac')
		stats = self.stats()
		for kind in ('lrc', 'txt', 'instrumental', 'none'):
			lyrics.write_lyrics(lyrics.Result(f, kind=kind), stats)
		assert [stats[k] for k in ('lrc', 'txt', 'instrumental', 'none')] == [1, 1, 1, 1]

	def test_a_save_error_is_logged_not_raised(
		self, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		with caplog.at_level(logging.ERROR):
			lyrics.write_lyrics(
				lyrics.Result(tmp_path / 'gone.flac', 'A', 'T', 'x', 'txt', 'new'), self.stats()
			)
		assert 'Could not save lyrics' in caplog.text

	def test_tags_written_after_the_lookup_are_kept(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		f = song(make_flac, tmp_path / 'a.flac')
		audio = FLAC(f)
		audio['LATE'] = ['kept']
		audio.save()
		lyrics.write_lyrics(lyrics.Result(f, 'A', 'T', 'x', 'txt', 'new'), self.stats())
		assert FLAC(f)['LATE'] == ['kept']


class TestRun:
	def album(
		self, make_flac: MakeFlac, root: Path, titles: tuple[str, ...] = ('One', 'Two')
	) -> Path:
		for i, t in enumerate(titles, 1):
			song(make_flac, root / f'{i:02d}.flac', TITLE=t, TRACKNUMBER=str(i))
		return root

	def test_every_track_is_fetched_and_written(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		a = self.album(make_flac, tmp_path / 'a')
		lookup = Lookup({'One': {'syncedLyrics': SYNCED}, 'Two': {'plainLyrics': 'words'}})
		with caplog.at_level(logging.INFO):
			lyrics.run(a, ctx, lookup, retry_rounds=())
		assert lyrics_of(a / '01.flac').splitlines()[-1] == '[00:05.45]Second line'
		assert lyrics_of(a / '02.flac') == 'Words'
		assert 'LRC: 1 TXT: 1 None: 0 Instrumental: 0 New: 2 Fixed: 0 Failed: 0' in caplog.text

	def test_a_second_run_changes_nothing(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		a = self.album(make_flac, tmp_path / 'a')
		lookup = Lookup({'One': {'syncedLyrics': SYNCED}, 'Two': {'plainLyrics': 'words'}})
		lyrics.run(a, ctx, lookup, retry_rounds=())
		before = [(f.stat().st_mtime_ns, f.stat().st_size) for f in sorted(a.glob('*.flac'))]
		with caplog.at_level(logging.INFO):
			lyrics.run(a, ctx, lookup, retry_rounds=())
		assert [
			(f.stat().st_mtime_ns, f.stat().st_size) for f in sorted(a.glob('*.flac'))
		] == before
		assert 'New: 0 Fixed: 0 Failed: 0' in caplog.text

	def test_albums_without_a_release_id_are_not_touched(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		make_flac(tmp_path / 'a' / '01.flac', ALBUMARTIST='A', TITLE='T')
		lookup = Lookup({'T': {'plainLyrics': 'x'}})
		lyrics.run(tmp_path / 'a', ctx, lookup, retry_rounds=())
		assert lookup.calls == []

	def test_a_track_lrclib_did_not_answer_is_retried_and_recovered(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		a = self.album(make_flac, tmp_path / 'a')
		answered: list[str] = []

		def lookup(params: dict[str, str]) -> dict | None:
			if params['track_name'] == 'Two' and 'Two' not in answered:
				answered.append('Two')
				return None  # first time: lrclib is throttling
			return {'plainLyrics': f'words of {params["track_name"]}'}

		with caplog.at_level(logging.INFO):
			lyrics.run(a, ctx, lookup, retry_rounds=((0, 2),))
		assert lyrics_of(a / '02.flac') == 'Words of Two'
		assert '1 tracks got no answer from lrclib; retrying' in caplog.text
		assert 'Failed: 0' in caplog.text.splitlines()[-1]  # recovered

	def test_a_track_that_never_gets_an_answer_is_left_alone_with_a_warning(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		a = self.album(make_flac, tmp_path / 'a', ('One',))
		f = FLAC(a / '01.flac')
		f['LYRICS'] = ['keep me']
		f.save()
		with caplog.at_level(logging.INFO):
			lyrics.run(a, ctx, lambda params: None, retry_rounds=((0, 1), (0, 1)))
		assert lyrics_of(a / '01.flac') == 'keep me'
		assert 'Lyrics not fetched, lrclib unavailable: Artist - One' in caplog.text
		assert 'Failed: 1' in caplog.text.splitlines()[-1]

	def test_stop_ends_the_step(self, ctx: Context, make_flac: MakeFlac, tmp_path: Path) -> None:
		a = self.album(make_flac, tmp_path / 'a')
		ctx.stop.set()
		with pytest.raises(Stopped):
			lyrics.run(a, ctx, Lookup({'One': {'plainLyrics': 'x'}}), retry_rounds=())
