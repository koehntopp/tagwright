"""LRC and lyric text rules, carried over from the discogs lrc_format.py (ADR 0006, 0036)."""

import pytest

from pipeline import lrc_format as f


@pytest.mark.parametrize(
	('text', 'synced', 'invalid'),
	[
		('[00:01.00]a', True, False),
		('plain words', False, False),
		('[0:01.00]a', False, False),  # not strict: one digit
		('[00:01]a', False, False),  # no hundredths
		('[100:00:01.00]a', False, True),  # HH:MM:SS style
		('', False, False),
	],
)
def test_lrc_detection(text: str, synced: bool, invalid: bool) -> None:
	assert f.is_lrc(text) is synced
	assert f.is_invalid_lrc(text) is invalid


def test_artist_is_the_albumartist_with_artist_as_fallback() -> None:
	assert f.resolve_artist('Album Artist', 'Track Artist') == 'Album Artist'
	assert f.resolve_artist('', 'Track Artist') == 'Track Artist'
	assert f.resolve_artist('', '') == ''


class TestHeaders:
	def test_make_headers_formats_the_length(self) -> None:
		assert f.make_headers('A', 'T', 'Al', 185.9) == '[ar:A]\n[ti:T]\n[al:Al]\n[length:03:05]\n'

	def test_missing_headers_are_inserted_at_the_top_in_order(self) -> None:
		assert (
			f.apply_headers('[00:01.00]hi', 'A', 'T', 'Al', 65)
			== '[ar:A]\n[ti:T]\n[al:Al]\n[length:01:05]\n[00:01.00]hi'
		)

	def test_existing_headers_are_refreshed_in_place(self) -> None:
		lrc = '[ti:Old]\n[00:01.00]hi\n[ar:Old Artist]'
		out = f.apply_headers(lrc, 'A', 'T', 'Al', 10)
		assert '[ti:T]' in out
		assert '[ti:Old]' not in out
		assert (
			out.index('[ti:T]') < out.index('[00:01.00]hi') < out.rindex('[ar:A]')
		)  # positions are kept

	def test_unmanaged_headers_pass_through_unchanged(self) -> None:
		out = f.apply_headers('[re:LRCLIB]\n[by:me]\n[offset:5]\n[00:01.00]hi', 'A', 'T', 'Al', 10)
		for keep in ('[re:LRCLIB]', '[by:me]', '[offset:5]'):
			assert keep in out.splitlines()

	def test_an_empty_fresh_value_never_blanks_an_existing_header(self) -> None:
		out = f.apply_headers('[ar:Keep]\n[ti:Keep]\n[00:01.00]hi', '', '', '', 0)
		assert '[ar:Keep]' in out
		assert '[ti:Keep]' in out
		assert '[al:' not in out  # nothing to insert without a value
		assert '[length:' not in out

	def test_applying_twice_changes_nothing(self) -> None:
		once = f.apply_headers('[00:01.00]hi', 'A', 'T', 'Al', 65)
		assert f.apply_headers(once, 'A', 'T', 'Al', 65) == once

	def test_blank_lines_are_dropped_and_the_result_is_stripped(self) -> None:
		assert (
			f.apply_headers('\n[00:01.00]a\n\n[00:02.00]b\n\n', '', '', '', 0)
			== '[00:01.00]a\n[00:02.00]b'
		)


class TestInstrumental:
	def test_canonical_block(self) -> None:
		marker = f.make_instrumental_lrc('A', 'T', 'Al', 65)
		assert marker.splitlines() == [
			'[ar:A]',
			'[ti:T]',
			'[al:Al]',
			'[length:01:05]',
			'[la:zxx]',
			'[instrumental:true]',
			'[00:00.00](Instrumental)',
		]
		assert f.is_instrumental_marker(marker)

	def test_the_block_replaces_existing_sentinel_headers_and_keeps_other_headers(self) -> None:
		once = f.build_instrumental_marker(['[ar:A]', '[re:x]', '[la:eng]', '[instrumental:false]'])
		assert once.splitlines()[:2] == ['[ar:A]', '[re:x]']
		assert once.count('[instrumental:true]') == 1
		assert '[la:eng]' not in once
		assert '[instrumental:false]' not in once
		# fed its own header lines again, the result is the same (the documented idempotence)
		headers = [x for x in once.splitlines() if x.startswith('[') and not x.startswith('[00:')]
		assert f.build_instrumental_marker(headers) == once

	@pytest.mark.parametrize(
		'text',
		[
			'[00:00.00][Instrumental]',
			'[00:01.50](instrumental)',
			'[00:00.00]  [INSTRUMENTAL]',
			'x\n[00:10.00](Instrumental)\ny',
		],
	)
	def test_hand_typed_markers_are_found(self, text: str) -> None:
		assert f.has_manual_instrumental_marker(text)

	@pytest.mark.parametrize(
		'text', ['Instrumental', '[Instrumental]', '[00:00.00]Instrumental', 'plain']
	)
	def test_other_text_is_not_a_manual_marker(self, text: str) -> None:
		assert not f.has_manual_instrumental_marker(text)

	@pytest.mark.parametrize(
		('lines', 'bare'),
		[
			(['Instrumental'], True),
			(['[Instrumental]'], True),
			(['(instrumental)'], True),
			(['Instrumental', 'x'], False),
			(['[00:00.00]Instrumental'], False),
			([], False),
		],
	)
	def test_bare_placeholder(self, lines: list[str], bare: bool) -> None:
		assert f.is_bare_instrumental_placeholder(lines) is bare


class TestNormalize:
	@pytest.mark.parametrize(
		('text', 'expected'),
		[
			('it’s', "it's"),
			('“quote”', '"quote"'),
			('a–b—c', 'a-b-c'),
			('wait…', 'wait...'),
			('a b c', 'a b c'),
			('zero​width﻿', 'zerowidth'),
			('don´t', "don't"),
			('don`t', "don't"),
			('`quoted`', '`quoted`'),  # not between two letters
			('café ♪', 'café ♪'),  # accents and music notes stay
			('plain', 'plain'),
		],
	)
	def test_normalize_text(self, text: str, expected: str) -> None:
		assert f.normalize_text(text) == expected
		assert f.normalize_text(f.normalize_text(text)) == expected  # idempotent

	def test_lrc_text_is_normalized_but_headers_are_not(self) -> None:
		lrc = '[ti:It’s]\n[00:01.00]It’s here\nuntimed — line'
		assert f.normalize_lrc_text(lrc).splitlines() == [
			'[ti:It’s]',
			"[00:01.00]It's here",
			'untimed - line',
		]


class TestCapitalize:
	def test_line(self) -> None:
		assert f.capitalize_line('  hello') == '  Hello'
		assert f.capitalize_line('été') == 'Été'
		assert f.capitalize_line('   ') == '   '
		assert f.capitalize_line('') == ''

	def test_lrc_strips_after_the_timestamp_and_capitalizes(self) -> None:
		assert (
			f.capitalize_lrc('[ar:x]\n[00:01.00]   hello\n[00:02.00]world')
			== '[ar:x]\n[00:01.00]Hello\n[00:02.00]World'
		)

	def test_txt(self) -> None:
		assert f.capitalize_txt('one\n\ntwo') == 'One\n\nTwo'


def lrc(lines: list[tuple[str, str]]) -> str:
	return '\n'.join(f'[{t}]{text}' for t, text in lines)


class TestSuspect:
	def test_body(self) -> None:
		assert f.lrc_body('[ti:x]\n[01:02.50]a\nplain\n[00:00.00] b ') == ([62.5, 0.0], ['a', ' b'])

	def test_sound_lrc_has_no_reasons(self) -> None:
		assert (
			f.lrc_suspect_reasons(
				lrc([('00:01.00', 'a'), ('00:05.00', 'b'), ('00:09.00', 'c')]), 12
			)
			== []
		)

	def test_too_few_lines_are_not_judged(self) -> None:
		assert f.lrc_suspect_reasons(lrc([('00:01.00', 'a'), ('00:01.00', 'b')]), 100) == []

	def test_instrumental_is_not_judged(self) -> None:
		assert (
			f.lrc_suspect_reasons('[instrumental:true]\n' + lrc([('00:00.00', 'a')] * 4), 100) == []
		)

	def test_one_timestamp(self) -> None:
		assert f.lrc_suspect_reasons(lrc([('00:01.00', 'a')] * 4)) == ['one_timestamp']

	def test_pile_up_needs_five_lines_and_a_fifth_of_all(self) -> None:
		pile = [('00:01.00', 'a')] * 5 + [(f'00:{10 + i}.00', 'b') for i in range(15)]
		assert f.lrc_suspect_reasons(lrc(pile)) == ['shared_timestamps']
		small = [('00:01.00', 'a')] * 4 + [(f'00:{10 + i}.00', 'b') for i in range(15)]
		assert f.lrc_suspect_reasons(lrc(small)) == []
		diluted = [('00:01.00', 'a')] * 5 + [(f'00:{10 + i}.00', 'b') for i in range(40)]
		assert f.lrc_suspect_reasons(lrc(diluted)) == []

	def test_ends_early_needs_a_length(self) -> None:
		early = lrc([('00:01.00', 'a'), ('00:05.00', 'b'), ('00:09.00', 'c')])
		assert f.lrc_suspect_reasons(early, 100) == ['ends_early']
		assert f.lrc_suspect_reasons(early, 0) == []
		assert (
			f.lrc_suspect_reasons(early, 18) == []
		)  # the last line is at half of the track: still fine

	def test_hearts_are_junk_but_music_notes_are_not(self) -> None:
		assert f.lrc_suspect_reasons(
			lrc([('00:01.00', 'a'), ('00:05.00', '♡ J&'), ('00:09.00', 'c')])
		) == ['junk_hearts']
		assert (
			f.lrc_suspect_reasons(lrc([('00:01.00', '♪'), ('00:05.00', 'b'), ('00:09.00', 'c')]))
			== []
		)

	def test_problem_lines_count_stacked_and_heart_lines(self) -> None:
		text = lrc(
			[('00:01.00', 'a')] * 3
			+ [('00:05.00', 'b')] * 2
			+ [('00:09.00', '♥ x'), ('00:10.00', 'c')]
		)
		assert f.lrc_problem_line_count(text) == 4  # three stacked + one heart; a pair is legal
		assert f.lrc_problem_line_count('[instrumental:true]\n' + text) == 0
		assert f.lrc_problem_line_count(lrc([('00:01.00', 'a')] * 2)) == 0
