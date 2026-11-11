"""Status model: six steps derived from tags, issue lines, album status (ADR 0006, 0016)."""

from pathlib import Path

import pytest
from mutagen.flac import FLAC

import app as tagwright

STEPS = ['Dynamic range', 'ReplayGain', 'Fingerprints', 'Tags and cover', 'Lyrics', 'Filenames']


def set_tag(album: Path, key: str, value: str | None, only_first: bool = False) -> None:
	"""Set (or with None remove) a tag on every file of the album, or on the first one."""
	for f in tagwright.flacs(album)[: 1 if only_first else None]:
		audio = FLAC(f)
		if value is None:
			audio.pop(key, None)
		else:
			audio[key] = [value]
		audio.save()


def done(s: dict) -> dict[str, bool]:
	return {step['name']: step['done'] for step in s['steps']}


def test_complete_album_is_fixed(album: Path) -> None:
	s = tagwright.summarize(album)
	assert [step['name'] for step in s['steps']] == STEPS
	assert all(done(s).values())
	assert s['issues'] == []
	assert s['status'] == 'fixed'
	assert s['steps_done'] == 6
	assert s['tracks'] == 2
	assert s['dr'] == '10'
	assert s['discogs'] == '12345'


@pytest.mark.parametrize(
	('key', 'step'),
	[
		('DYNAMIC_RANGE', 'Dynamic range'),
		('REPLAYGAIN_ALBUM_GAIN', 'ReplayGain'),
		('ACOUSTID_FINGERPRINT', 'Fingerprints'),
		('VERSION', 'Tags and cover'),
		('LYRICS', 'Lyrics'),
	],
)
def test_a_missing_tag_reopens_exactly_its_step(album: Path, key: str, step: str) -> None:
	set_tag(album, key, None, only_first=True)  # one track missing it is enough
	s = tagwright.summarize(album)
	assert {name: ok for name, ok in done(s).items() if not ok} == {step: False}


def test_legacy_spaced_fingerprint_key_still_counts(album: Path) -> None:
	set_tag(album, 'ACOUSTID_FINGERPRINT', None)
	set_tag(album, 'ACOUSTID FINGERPRINT', 'AQAA')
	assert done(tagwright.summarize(album))['Fingerprints']


def test_a_step_gap_makes_the_album_ready_not_needs(album: Path) -> None:
	set_tag(album, 'REPLAYGAIN_ALBUM_GAIN', None)
	s = tagwright.summarize(album)
	assert s['issues'] == []
	assert s['status'] == 'ready'


def test_wrong_file_name_reopens_filenames(album: Path) -> None:
	first = tagwright.flacs(album)[0]
	first.rename(first.with_name('renamed.flac'))
	assert done(tagwright.summarize(album))['Filenames'] is False


def test_plain_lyrics_are_done_but_partial(album: Path) -> None:
	set_tag(album, 'LYRICS', 'plain words', only_first=True)
	s = tagwright.summarize(album)
	lyrics = next(step for step in s['steps'] if step['name'] == 'Lyrics')
	assert lyrics['done']
	assert lyrics['partial']
	assert s['lyrics'] == {'synced': 1, 'plain': 1, 'instrumental': 0, 'missing': 0}


def test_without_discogs_id_the_only_blocker_is_the_red_discogs_line(album: Path) -> None:
	set_tag(album, 'DISCOGS_RELEASE_ID', None)
	set_tag(album, 'ALBUM_FORMAT', None)  # would be a second line with an ID
	s = tagwright.summarize(album)
	assert s['status'] == 'needs'
	assert [i['level'] for i in s['issues']] == ['error']
	assert s['issues'][0]['action'] == 'search'
	assert done(s)['Tags and cover'] is False


def test_empty_required_tag_blocks_the_album(album: Path) -> None:
	set_tag(album, 'ALBUM_FORMAT', None)
	s = tagwright.summarize(album)
	assert s['status'] == 'needs'
	assert any(i['level'] == 'warn' for i in s['issues'])


def test_files_that_disagree_on_an_album_tag_block_the_album(album: Path) -> None:
	set_tag(album, 'ALBUM_FORMAT', 'Vinyl', only_first=True)
	s = tagwright.summarize(album)
	assert s['status'] == 'needs'
	assert any('disagree' in i['text'] for i in s['issues'])


def test_duplicate_track_numbers_are_flagged(album: Path) -> None:
	set_tag(album, 'TRACKNUMBER', '1')
	s = tagwright.summarize(album)
	assert any('more than one file' in i['text'] for i in s['issues'])


def test_discogs_error_line_is_listed_first(album: Path) -> None:
	set_tag(album, 'DISCOGS_RELEASE_ID', '1', only_first=True)
	set_tag(album, 'DISCOGS_RELEASE_ID', '2')  # then the files disagree after the second pass
	set_tag(album, 'DISCOGS_RELEASE_ID', '3', only_first=True)
	set_tag(album, 'ALBUM_FORMAT', None, only_first=True)
	levels = [i['level'] for i in tagwright.summarize(album)['issues']]
	assert levels[0] == 'error'
	assert levels == sorted(levels, key=lambda lv: lv != 'error')


def test_small_cover_blocks_only_the_move(album: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(tagwright, 'MIN_COVER', 1400)  # the fixture has no cover at all
	s = tagwright.summarize(album)
	assert s['status'] == 'fixed'
	assert [i['level'] for i in s['issues']] == ['ingest']
	step = next(step for step in s['steps'] if step['name'] == 'Tags and cover')
	assert step['done']
	assert step['partial']


def test_summary_cache_follows_file_changes(album: Path) -> None:
	assert tagwright.get_summary(album)['status'] == 'fixed'
	set_tag(album, 'DYNAMIC_RANGE', None, only_first=True)
	assert tagwright.fresh_summary(album)['status'] == 'ready'


def test_album_without_flac_is_404() -> None:
	empty = tagwright.ROOT / 'empty'
	empty.mkdir()
	with pytest.raises(Exception, match='404'):
		tagwright.summarize(empty)
