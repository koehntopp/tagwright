"""fixtags: the pure parts, carried over from the discogs fixtags.py with their edge cases (ADR 0014, 0036)."""

import logging

import pytest

from pipeline import fixtags
from pipeline.http import ApiError


@pytest.mark.parametrize(
	('text', 'key'),
	[
		('Glass Mastered At', 'P_GLASS_MASTERED_AT'),
		('  pressed  by ', 'P_PRESSED_BY'),
		('Matrix / Runout', 'P_MATRIX_RUNOUT'),
		('Mastering SID Code', 'P_MASTERING_SID_CODE'),
		('', ''),
		('---', ''),
		('ünï', 'P_N'),  # non-ASCII letters are not part of a tag key
	],
)
def test_tag_key(text: str, key: str) -> None:
	assert fixtags.tag_key('P_', text) == key


@pytest.mark.parametrize(
	('name', 'cleaned'),
	[
		('Artist (2)', 'Artist'),
		('Artist (12)', 'Artist'),
		('  Plain  ', 'Plain'),
		('A (B)', 'A (B)'),
		('X (2) Y', 'X (2) Y'),
	],
)
def test_clean_name_drops_only_the_trailing_number(name: str, cleaned: str) -> None:
	assert fixtags.clean_name(name) == cleaned


class TestExtraTags:
	def test_empty_release_has_no_extra_tags(self) -> None:
		assert fixtags.discogs_extra_tags({}) == {}
		assert fixtags.discogs_extra_tags({'companies': None, 'labels': None}) == {}

	def test_companies_become_one_tag_per_role_without_disambiguation(self) -> None:
		data = {
			'companies': [
				{'entity_type_name': 'Pressed By', 'name': 'Sony DADC (2)'},
				{'entity_type_name': 'Pressed By', 'name': 'MPO'},
				{'entity_type_name': 'Pressed By', 'name': 'MPO'},  # duplicate
				{'entity_type_name': 'Mastered At', 'name': 'Abbey Road'},
				{'entity_type_name': '', 'name': 'No Role'},  # no usable key
				{'entity_type_name': 'Glass Mastered At', 'name': ''},  # no value
			]
		}
		assert fixtags.discogs_extra_tags(data) == {
			'ALBUM_COMPANY_PRESSED_BY': ['Sony DADC', 'MPO'],
			'ALBUM_COMPANY_MASTERED_AT': ['Abbey Road'],
		}

	def test_credits_keep_the_role_detail_and_split_multiple_roles(self) -> None:
		data = {
			'extraartists': [
				{'name': 'Jane (3)', 'role': 'Mastered By [Digital]'},
				{'name': 'Bob', 'role': 'Producer, Engineer'},
				{'name': 'Bob', 'role': 'Engineer'},  # same person, same role again
				{'name': '', 'role': 'Mixed By [Studio A]'},  # no name: nothing to write
				{'name': 'Cy', 'role': ''},  # no role: no key
			]
		}
		assert fixtags.discogs_extra_tags(data) == {
			'ALBUM_CREDIT_MASTERED_BY': ['Jane [Digital]'],
			'ALBUM_CREDIT_PRODUCER': ['Bob'],
			'ALBUM_CREDIT_ENGINEER': ['Bob'],
		}

	def test_identifiers_append_their_description(self) -> None:
		data = {
			'identifiers': [
				{'type': 'Matrix / Runout', 'value': 'ABC 1', 'description': 'Side A'},
				{'type': 'Matrix / Runout', 'value': 'ABC 2'},
				{'type': 'Barcode', 'value': '123'},
				{'type': 'Barcode', 'value': '  ', 'description': 'blank'},  # no value
				{'type': '', 'value': 'x'},  # no key
				{'type': 'Other', 'description': 'only a description'},  # no value
			]
		}
		assert fixtags.discogs_extra_tags(data) == {
			'ALBUM_IDENT_MATRIX_RUNOUT': ['ABC 1 (Side A)', 'ABC 2'],
			'ALBUM_IDENT_BARCODE': ['123'],
		}

	def test_labels_and_catalog_numbers_skip_none(self) -> None:
		data = {
			'labels': [
				{'name': 'Island (2)', 'catno': 'CAT-1'},
				{'name': 'Island (2)', 'catno': 'NONE'},  # any case
				{'name': 'Other', 'catno': ' '},
				{'name': 'Third', 'catno': 'CAT-1'},  # duplicate catno
			]
		}
		assert fixtags.discogs_extra_tags(data) == {
			'ALBUM_RELEASE_LABELS': ['Island', 'Other', 'Third'],
			'ALBUM_RELEASE_CATALOGNUMBERS': ['CAT-1'],
		}

	def test_format_genres_styles_series_notes_and_dates(self) -> None:
		data = {
			'formats': [
				{'name': 'CD', 'descriptions': ['Album', 'Reissue'], 'text': 'Digipak'},
				{'name': 'DVD', 'descriptions': None},
			],
			'genres': ['Rock', 'Rock'],
			'styles': ['Indie'],
			'series': [{'name': 'Deluxe Series'}, {'name': ''}],
			'notes': '  Some notes  ',
			'released': '2020-02-03',
			'data_quality': 'Correct',
		}
		assert fixtags.discogs_extra_tags(data) == {
			'ALBUM_RELEASE_FORMAT': ['CD', 'DVD'],
			'ALBUM_RELEASE_FORMAT_DESCRIPTIONS': ['Album', 'Reissue'],
			'ALBUM_RELEASE_FORMAT_TEXT': ['Digipak'],
			'ALBUM_RELEASE_GENRES': ['Rock'],
			'ALBUM_RELEASE_STYLES': ['Indie'],
			'ALBUM_RELEASE_SERIES': ['Deluxe Series'],
			'ALBUM_RELEASE_NOTES': ['Some notes'],
			'ALBUM_RELEASE_DATE_FULL': ['2020-02-03'],
			'ALBUM_RELEASE_DATA_QUALITY': ['Correct'],
		}


@pytest.mark.parametrize(
	('rate', 'text'),
	[
		(44100, '44.1kHz'),
		(48000, '48kHz'),
		(88200, '88.2kHz'),
		(96000, '96kHz'),
		(176400, '176.4kHz'),
		(192000, '192kHz'),
		(0, '44.1kHz'),  # unreadable file
		(-1, '44.1kHz'),
	],
)
def test_max_resolution(rate: int, text: str) -> None:
	assert fixtags.max_resolution(rate) == text


@pytest.mark.parametrize(
	('args', 'expected'),
	[
		((2020, '07', 'CD', '', ''), '2020 DR07 CD'),
		((2020, '7', 'CD', 'Deluxe', 'CAT-1'), '2020 DR07 CD (Deluxe) (CAT-1)'),
		((2020, '', 'CD', '', ''), '2020 CD'),
		((2020, 'abc', 'CD', '', ''), '2020 CD'),  # a DR that is not a number is left out
		((0, '10', 'Vinyl', '', 'X'), 'DR10 Vinyl (X)'),  # no year
		((0, '', '', '', ''), ''),
		((1999, '12', '', 'Remaster', ''), '1999 DR12 (Remaster)'),
	],
)
def test_version_string(args: tuple[int, str, str, str, str], expected: str) -> None:
	assert fixtags.version_string(*args) == expected


def test_first_value_skips_missing_empty_and_empty_lists() -> None:
	tags = {'A': [], 'B': [''], 'C': ['x'], 'D': ['y']}
	assert fixtags.first_value(tags, 'A', 'B', 'C', 'D') == 'x'
	assert fixtags.first_value(tags, 'A', 'B', 'Z') == ''
	assert fixtags.first_value({}, 'A') == ''


RELEASE = {'id': 7, 'title': ' Release Title ', 'year': 2020, 'master_id': 99}


def plan(
	first: dict[str, list[str]] | None = None,
	release: dict | None = None,
	year_master: int = 2001,
	max_rate_hz: int = 44100,
) -> fixtags.Plan:
	return fixtags.plan_tags(
		first or {}, release or RELEASE, {}, 'Master Title', year_master, max_rate_hz
	)


class TestPlanTags:
	def test_basic_tags(self) -> None:
		p = plan({'ALBUM_DR': ['7'], 'ALBUM_FORMAT': ['Vinyl'], 'CATALOGNUMBER': ['CAT-1']})
		t = p.tags
		assert t['ALBUM'] == ['Master Title']
		assert t['ORIGINAL_TITLE'] == ['Master Title']
		assert t['ALBUM_MASTER_TITLE'] == ['Master Title']
		assert t['ALBUM_RELEASE_TITLE'] == ['Release Title']  # stripped
		assert t['VERSION'] == ['2020 DR07 Vinyl (CAT-1)']
		assert p.version == '2020 DR07 Vinyl (CAT-1)'
		for key in ('RELEASEDATE', 'DATE', 'YEAR', 'ALBUM_RELEASE_YEAR'):
			assert t[key] == ['2020']
		for key in (
			'ORIGINALDATE',
			'ORIGINALRELEASEDATE',
			'ORIGINAL DATE',
			'ORIGINAL YEAR',
			'ALBUM_MASTER_YEAR',
		):
			assert t[key] == ['2001']
		assert t['ALBUM_FORMAT'] == ['Vinyl']
		assert t['ALBUM_DR'] == ['7']  # copied as it is
		assert t['ALBUM_MAX_RESOLUTION'] == ['44.1kHz']

	def test_title_override_wins_over_the_master_title(self) -> None:
		p = plan({'ALBUM_TITLE_OVERRIDE': ['My Title']})
		assert p.album_name == 'My Title'
		assert p.tags['ALBUM'] == ['My Title']
		assert p.tags['ORIGINAL_TITLE'] == ['Master Title']  # the Discogs title stays

	def test_artist_override_is_written_only_when_set(self) -> None:
		assert 'ALBUMARTIST' not in plan({}).tags
		assert 'ALBUMARTIST' not in plan({'ALBUM_ARTIST_OVERRIDE': ['  ']}).tags
		assert plan({'ALBUM_ARTIST_OVERRIDE': [' New Name ']}).tags['ALBUMARTIST'] == ['New Name']

	@pytest.mark.parametrize(
		('release_year', 'master_year', 'date', 'original'),
		[
			(2020, 2001, '2020', '2001'),
			(0, 2001, '2001', '2001'),  # no release year: the master's
			(2020, 0, '2020', '2020'),  # no master year: the release's
			(0, 0, '0', '0'),
		],
	)
	def test_year_fallbacks(
		self, release_year: int, master_year: int, date: str, original: str
	) -> None:
		p = plan(release={**RELEASE, 'year': release_year}, year_master=master_year)
		assert p.tags['DATE'] == [date]
		assert p.tags['ORIGINALDATE'] == [original]

	def test_release_year_tag_only_with_a_real_release_year(self) -> None:
		assert 'ALBUM_RELEASE_YEAR' not in plan(release={**RELEASE, 'year': 0}).tags
		assert 'ALBUM_RELEASE_YEAR' not in plan(release={**RELEASE, 'year': None}).tags

	def test_the_year_never_comes_from_tags_already_written(self) -> None:
		p = plan({'DATE': ['1999'], 'YEAR': ['1999'], 'ALBUM_RELEASE_YEAR': ['1999']})
		assert p.tags['DATE'] == ['2020']

	def test_format_falls_back_to_subtitle_then_cd(self) -> None:
		assert plan({'ALBUM_FORMAT': ['SACD'], 'SUBTITLE': ['x']}).tags['ALBUM_FORMAT'] == ['SACD']
		assert plan({'SUBTITLE': [' Vinyl ']}).tags['ALBUM_FORMAT'] == ['Vinyl']
		assert plan({}).tags['ALBUM_FORMAT'] == ['CD']
		assert plan({'ALBUM_FORMAT': ['']}).tags['ALBUM_FORMAT'] == ['CD']

	@pytest.mark.parametrize(
		'key', ['CATALOGNUMBER', 'CATALOG NUMBER', 'CATALOG_NUMBER', 'CATALOGNO']
	)
	def test_catalog_number_spellings(self, key: str) -> None:
		assert plan({key: [' CAT-9 ']}).version.endswith('(CAT-9)')

	def test_catalog_number_first_spelling_wins(self) -> None:
		assert plan({'CATALOGNO': ['B'], 'CATALOGNUMBER': ['A']}).version.endswith('(A)')

	def test_edition_and_dr_are_optional_tags(self) -> None:
		t = plan({}).tags
		assert 'ALBUM_EDITION' not in t
		assert 'ALBUM_DR' not in t
		t = plan({'ALBUM_EDITION': ['Deluxe'], 'ALBUM_DR': ['09']}).tags
		assert t['ALBUM_EDITION'] == ['Deluxe']
		assert t['ALBUM_DR'] == ['09']

	def test_country_and_first_label(self) -> None:
		t = plan(
			release={
				**RELEASE,
				'country': ' UK ',
				'labels': [{'name': ' Island '}, {'name': 'Other'}],
			}
		).tags
		assert t['ALBUM_RELEASE_COUNTRY'] == ['UK']
		assert t['ALBUM_RELEASE_LABEL'] == ['Island']

	@pytest.mark.parametrize(
		'release',
		[
			{},
			{'country': None, 'labels': []},
			{'country': ' ', 'labels': [{}]},
			{'labels': [{'name': ' '}]},
		],
	)
	def test_country_and_label_are_skipped_without_a_value(self, release: dict) -> None:
		t = plan(release={**RELEASE, **release}).tags
		assert 'ALBUM_RELEASE_COUNTRY' not in t
		assert 'ALBUM_RELEASE_LABEL' not in t

	def test_extra_tags_are_merged_and_win_over_basics(self) -> None:
		t = plan(
			release={**RELEASE, 'genres': ['Rock'], 'labels': [{'name': 'L', 'catno': 'C'}]}
		).tags
		assert t['ALBUM_RELEASE_GENRES'] == ['Rock']
		assert t['ALBUM_RELEASE_LABELS'] == ['L']

	def test_unmappable_extra_fields_only_cost_the_extra_tags(
		self, caplog: pytest.LogCaptureFixture
	) -> None:
		with caplog.at_level(logging.WARNING):
			p = plan(release={**RELEASE, 'companies': 'not a list of dicts'})
		assert 'Could not map extra Discogs fields' in caplog.text
		assert p.tags['ALBUM'] == ['Master Title']  # everything else is intact


class FakeGet:
	"""A Discogs `get` that plays back answers by path (an exception is raised) and records the calls."""

	def __init__(self, answers: dict[str, dict | Exception]) -> None:
		self.answers = answers
		self.calls: list[str] = []

	def __call__(self, path: str) -> dict:
		self.calls.append(path)
		answer = self.answers[path]
		if isinstance(answer, Exception):
			raise answer
		return answer


def get_of(answers: dict[str, dict | Exception]) -> FakeGet:
	return FakeGet(answers)


class TestMaster:
	def test_no_master_id_uses_the_release_title_and_makes_no_request(self) -> None:
		get = get_of({})
		assert fixtags.fetch_master(get, {'title': ' T '}) == (None, 'T')
		assert get.calls == []

	def test_master_title_is_used(self) -> None:
		get = get_of({'/masters/5': {'title': ' Master '}})
		assert fixtags.fetch_master(get, {'title': 'T', 'master_id': 5}) == (
			{'title': ' Master '},
			'Master',
		)

	@pytest.mark.parametrize(
		'answer', [ApiError(404, 'x'), ApiError(429, 'x'), {}, {'title': None}]
	)
	def test_a_master_that_cannot_be_had_falls_back_to_the_release_title(
		self, answer: dict | Exception
	) -> None:
		get = get_of({'/masters/5': answer})
		assert fixtags.fetch_master(get, {'title': 'T', 'master_id': 5}) == (None, 'T')

	def test_master_year_comes_from_the_main_release(self) -> None:
		get = get_of({'/releases/42': {'year': 1991}})
		assert fixtags.master_year(get, {'main_release': 42}, 2020, 1) == 1991

	def test_master_year_is_the_release_year_without_a_master(self) -> None:
		assert fixtags.master_year(get_of({}), None, 2020, 1) == 2020

	@pytest.mark.parametrize('answer', [ApiError(502, 'x'), {'year': 'n/a'}])
	def test_master_year_falls_back_with_a_warning(
		self, answer: dict | Exception, caplog: pytest.LogCaptureFixture
	) -> None:
		get = get_of({'/releases/42': answer})
		with caplog.at_level(logging.WARNING):
			assert fixtags.master_year(get, {'main_release': 42}, 2020, 1) == 2020
		assert 'Could not fetch master release year' in caplog.text

	def test_master_without_main_release_falls_back(self) -> None:
		assert fixtags.master_year(get_of({}), {}, 2020, 1) == 2020

	def test_a_missing_year_is_zero(self) -> None:
		get = get_of({'/releases/42': {'year': None}})
		assert fixtags.master_year(get, {'main_release': 42}, 2020, 1) == 0
