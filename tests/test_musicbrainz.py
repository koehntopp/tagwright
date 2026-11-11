"""MusicBrainz languages: parsing, caching, track matching and LYRICS_LANGUAGE (ADR 0023, 0036)."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from mutagen.flac import FLAC

from pipeline import languages, musicbrainz
from pipeline.config import Config
from pipeline.http import ApiError

from .conftest import MakeFlac

RAW = {
	'text-representation': {'language': 'eng'},
	'media': [
		{
			'position': 1,
			'tracks': [
				{
					'id': 't1',
					'position': 1,
					'title': 'Hello World',
					'recording': {
						'relations': [
							{'work': {'languages': ['eng', 'deu']}},
							{'work': {'language': 'eng'}},  # duplicate language
							{'work': {'language': 'fra'}},  # single-language form
							{'work': {}},  # work without a language
							{'type': 'other'},  # not a work relation
						]
					},
				},
				{
					'id': 't2',
					'position': 2,
					'title': 'Instrumental',
					'recording': {'relations': []},
				},
				{'id': 't3', 'position': 3, 'title': 'No Recording'},
			],
		},
		{
			'position': 2,
			'tracks': [{'id': 't4', 'position': 1, 'title': 'Disc Two', 'recording': {}}],
		},
	],
}


def test_work_languages_union_in_order() -> None:
	assert musicbrainz.work_languages(RAW['media'][0]['tracks'][0]['recording']) == [
		'eng',
		'deu',
		'fra',
	]
	assert musicbrainz.work_languages({}) == []


def test_parse_release_has_one_entry_per_track() -> None:
	release = musicbrainz.parse_release(RAW)
	assert release['release_language'] == 'eng'
	assert [(t['id'], t['disc'], t['position']) for t in release['tracks']] == [
		('t1', 1, 1),
		('t2', 1, 2),
		('t3', 1, 3),
		('t4', 2, 1),
	]
	assert release['tracks'][0]['languages'] == ['eng', 'deu', 'fra']
	assert release['tracks'][2]['languages'] == []
	assert musicbrainz.parse_release({}) == {'release_language': None, 'tracks': []}


class TestFindTrack:
	release = musicbrainz.parse_release(RAW)

	def test_by_release_track_id(self) -> None:
		assert self.release['tracks'][1] == musicbrainz.find_track(
			self.release, 't2', 9, 9, 'whatever'
		)

	def test_by_position_when_the_title_agrees(self) -> None:
		found = musicbrainz.find_track(self.release, '', 1, 1, 'hello, world!')
		assert found is not None
		assert found['id'] == 't1'

	def test_by_position_is_refused_when_the_title_differs(self) -> None:
		assert musicbrainz.find_track(self.release, '', 1, 1, 'Completely Different') is None

	def test_unknown_id_falls_back_to_the_position(self) -> None:
		found = musicbrainz.find_track(self.release, 'nope', 2, 1, 'Disc Two')
		assert found is not None
		assert found['id'] == 't4'

	def test_unknown_position(self) -> None:
		assert musicbrainz.find_track(self.release, '', 5, 5, 'x') is None


class TestReleaseLanguages:
	def fake_fetch(self, monkeypatch: pytest.MonkeyPatch, result: dict | None) -> list[str]:
		calls: list[str] = []

		def fetch(mbid: str) -> dict | None:
			calls.append(mbid)
			return result

		monkeypatch.setattr(musicbrainz, 'fetch_release', fetch)
		return calls

	def test_fetches_parses_and_caches(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		calls = self.fake_fetch(monkeypatch, RAW)
		cache = tmp_path / 'mb'
		first = musicbrainz.release_languages('abc', cache)
		assert first is not None
		assert first['tracks'][0]['id'] == 't1'
		assert (cache / 'abc.json').is_file()
		assert musicbrainz.release_languages('abc', cache) == first
		assert calls == ['abc']  # the second call came from the cache

	def test_refresh_asks_again(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
		calls = self.fake_fetch(monkeypatch, RAW)
		musicbrainz.release_languages('abc', tmp_path)
		musicbrainz.release_languages('abc', tmp_path, refresh=True)
		assert calls == ['abc', 'abc']

	def test_a_stale_cache_is_ignored(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		old = (datetime.now() - timedelta(days=musicbrainz.CACHE_DAYS + 1)).isoformat()
		(tmp_path / 'abc.json').write_text(json.dumps({'fetched': old, 'release': {'tracks': []}}))
		calls = self.fake_fetch(monkeypatch, RAW)
		release = musicbrainz.release_languages('abc', tmp_path)
		assert calls == ['abc']
		assert release is not None
		assert release['tracks']

	@pytest.mark.parametrize(
		'content', ['not json', '{}', '{"fetched": "yesterday", "release": {}}']
	)
	def test_an_unreadable_cache_is_ignored(
		self, content: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		(tmp_path / 'abc.json').write_text(content)
		calls = self.fake_fetch(monkeypatch, RAW)
		assert musicbrainz.release_languages('abc', tmp_path) is not None
		assert calls == ['abc']

	def test_a_failed_lookup_is_none_and_not_cached(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		self.fake_fetch(monkeypatch, None)
		assert musicbrainz.release_languages('abc', tmp_path / 'mb') is None
		assert not (tmp_path / 'mb').exists()


def test_fetch_release_asks_for_work_languages(monkeypatch: pytest.MonkeyPatch) -> None:
	seen: dict = {}

	def get(path: str, **params: str | int) -> dict:
		seen.update(path=path, **params)
		return RAW

	monkeypatch.setattr(musicbrainz, 'get', get)
	assert musicbrainz.fetch_release('abc') == RAW
	assert seen['path'] == '/release/abc'
	assert (
		seen['inc'] == 'recordings+recording-level-rels+work-rels'
	)  # without recording-level-rels no languages come back


def test_fetch_release_failure_is_none_not_no_language(
	monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
	def get(path: str, **params: str | int) -> dict:
		raise ApiError(429, 'MusicBrainz rate limit reached')

	monkeypatch.setattr(musicbrainz, 'get', get)
	with caplog.at_level(logging.WARNING):
		assert musicbrainz.fetch_release('abc') is None
	assert 'MusicBrainz lookup failed' in caplog.text


class TestLanguageTags:
	def test_release_id_spellings_and_strip(self) -> None:
		assert languages.release_id({'MUSICBRAINZ_ALBUMID': [' abc ']}) == 'abc'
		assert languages.release_id({'MUSICBRAINZ ALBUM ID': ['def']}) == 'def'
		assert (
			languages.release_id({'MUSICBRAINZ_ALBUMID': ['  '], 'MUSICBRAINZ ALBUM ID': ['x']})
			== 'x'
		)
		assert (
			languages.release_id({'MUSICBRAINZ_RELEASEGROUPID': ['rg']}) == ''
		)  # not the release-group id
		assert languages.release_id({}) == ''

	def test_load_release_is_off_without_id_or_when_switched_off(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		def boom(*a: object) -> dict:
			raise AssertionError('MusicBrainz must not be asked')

		monkeypatch.setattr(musicbrainz, 'release_languages', boom)
		assert languages.load_release({}, Config(tmp_path)) is None
		assert (
			languages.load_release(
				{'MUSICBRAINZ_ALBUMID': ['abc']}, Config(tmp_path, musicbrainz_languages=False)
			)
			is None
		)

	def test_load_release_uses_the_cache_directory_in_data(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		seen: list[tuple] = []

		def fake(mbid: str, cache_dir: Path, refresh: bool) -> dict:
			seen.append((mbid, cache_dir, refresh))
			return {'tracks': []}

		monkeypatch.setattr(musicbrainz, 'release_languages', fake)
		languages.load_release({'MUSICBRAINZ_ALBUMID': ['abc']}, Config(tmp_path), refresh=True)
		assert seen == [('abc', tmp_path / 'musicbrainz', True)]

	def test_load_release_failure_warns_and_leaves_tags(
		self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
	) -> None:
		monkeypatch.setattr(musicbrainz, 'release_languages', lambda *a: None)
		with caplog.at_level(logging.WARNING):
			assert (
				languages.load_release({'MUSICBRAINZ_ALBUMID': ['abc']}, Config(tmp_path)) is None
			)
		assert 'left as it is' in caplog.text

	@pytest.fixture
	def release(self) -> dict:
		return musicbrainz.parse_release(RAW)

	def flac(self, make_flac: MakeFlac, tmp_path: Path, **tags: str) -> FLAC:
		return FLAC(make_flac(tmp_path / 'a.flac', **tags))

	def test_sets_the_languages_of_the_matched_track(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(make_flac, tmp_path, TITLE='Hello World', TRACKNUMBER='1', DISCNUMBER='1')
		assert languages.apply_language(audio, release) is True
		assert audio['LYRICS_LANGUAGE'] == ['eng', 'deu', 'fra']
		assert languages.apply_language(audio, release) is False  # already up to date

	def test_matches_by_track_id_before_position(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac, tmp_path, MUSICBRAINZ_RELEASETRACKID=' t1 ', TITLE='x', TRACKNUMBER='9'
		)
		assert languages.apply_language(audio, release) is True

	def test_position_with_total_is_understood(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac, tmp_path, TITLE='Hello World', TRACKNUMBER='1/3', DISCNUMBER='1/2'
		)
		assert languages.apply_language(audio, release) is True

	def test_missing_numbers_default_to_disc_1_track_0(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac, tmp_path, TITLE='Hello World', TRACKNUMBER='junk', DISCNUMBER='junk'
		)
		assert languages.apply_language(audio, release) is False  # disc 1, track 0 does not exist

	def test_an_unmatched_file_keeps_what_it_has(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac,
			tmp_path,
			TITLE='Other Edition Song',
			TRACKNUMBER='1',
			DISCNUMBER='1',
			LYRICS_LANGUAGE='spa',
		)
		assert languages.apply_language(audio, release) is False
		assert audio['LYRICS_LANGUAGE'] == ['spa']

	def test_a_matched_track_without_language_loses_the_tag(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac,
			tmp_path,
			TITLE='Instrumental',
			TRACKNUMBER='2',
			DISCNUMBER='1',
			LYRICS_LANGUAGE='eng',
		)
		assert languages.apply_language(audio, release) is True
		assert 'LYRICS_LANGUAGE' not in audio.tags

	def test_a_matched_track_without_language_and_tag_changes_nothing(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(
			make_flac, tmp_path, TITLE='Instrumental', TRACKNUMBER='2', DISCNUMBER='1'
		)
		assert languages.apply_language(audio, release) is False

	def test_no_release_or_no_tags_changes_nothing(
		self, release: dict, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		audio = self.flac(make_flac, tmp_path, TITLE='Hello World')
		assert languages.apply_language(audio, None) is False
		audio.tags = None
		assert languages.apply_language(audio, release) is False
