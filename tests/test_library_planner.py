"""The library layout: the default template equals bliss.py, and the planner's rules (ADR 0037, 0010)."""

import json
from pathlib import Path, PurePosixPath

import pytest

from library import planner, template
from library.planner import Item
from library.template import Chip, Template

GOLDEN = json.loads((Path(__file__).parent / 'data' / 'bliss_golden.json').read_text())


def items(album: dict, prefix: str = '') -> list[Item]:
	return [
		Item(PurePosixPath(f'{prefix}in/{album["name"]}_{i}.flac'), f['tags'])
		for i, f in enumerate(album['files'])
	]


@pytest.mark.parametrize('album', GOLDEN, ids=[a['name'] for a in GOLDEN])
def test_the_default_template_gives_what_bliss_gives(album: dict) -> None:
	"""bliss_golden.json was produced by running the discogs bliss.py (get_target_path_and_filename and
	multi_disc_albums) on these tags once; Tagwright must name files exactly the same."""
	plan = planner.plan(items(album), template.default())
	assert not plan.unplaced
	assert not plan.skipped
	assert sorted(str(m.dst) for m in plan.moves) == sorted(f['expected'] for f in album['files'])


def tags(**kw: str) -> dict[str, str]:
	return {
		'ALBUMARTIST': 'A',
		'ALBUM': 'Al',
		'TITLE': 'T',
		'TRACKNUMBER': '1',
		'DISCNUMBER': '1',
		**kw,
	}


def run(
	files: dict[str, dict[str, str]],
	t: Template | None = None,
	discs: set[tuple[str, ...]] | None = None,
) -> planner.Plan:
	return planner.plan(
		[Item(PurePosixPath(p), x) for p, x in files.items()],
		t or template.default(),
		lambda d: d in (discs or set()),
	)


class TestRules:
	def test_a_file_in_place_is_not_moved(self) -> None:
		p = run({'A/Al/01_01_T.flac': tags()})
		assert (p.moves, p.in_place) == ([], 1)

	def test_an_empty_tag_leaves_the_file_unplaced_without_a_placeholder(self) -> None:
		p = run(
			{
				'x.flac': tags(TITLE=''),
				'y.flac': {**tags(), 'DISCNUMBER': ''},
				'z.flac': tags(ALBUMARTIST='', ARTIST='Fallback Artist'),
			}
		)
		assert p.moves == []
		assert {str(u.path): u.reason for u in p.unplaced} == {
			'x.flac': 'TITLE is empty',
			'y.flac': 'DISCNUMBER is empty',
			'z.flac': 'ALBUMARTIST is empty',  # ADR 0010: ARTIST is not a fallback
		}

	def test_a_name_that_is_empty_after_cleaning_is_unplaced(self) -> None:
		p = run({'x.flac': tags(ALBUM='???')})
		assert 'empty after cleaning' in p.unplaced[0].reason

	def test_a_later_single_disc_file_joins_an_existing_multi_disc_album(self) -> None:
		p = run({'x.flac': tags()}, discs={('A', 'Al')})
		assert str(p.moves[0].dst) == 'A/Al/Disc 1/01_01_T.flac'

	def test_one_file_of_disc_two_makes_the_whole_album_multi_disc(self) -> None:
		p = run({'a.flac': tags(), 'b.flac': tags(DISCNUMBER='2', TITLE='U')})
		assert sorted(str(m.dst) for m in p.moves) == [
			'A/Al/Disc 1/01_01_T.flac',
			'A/Al/Disc 2/02_01_U.flac',
		]

	def test_albums_are_judged_each_by_themselves(self) -> None:
		p = run({'a.flac': tags(ALBUM='One'), 'b.flac': tags(ALBUM='Two', DISCNUMBER='2')})
		assert sorted(str(m.dst) for m in p.moves) == [
			'A/One/01_01_T.flac',
			'A/Two/Disc 2/02_01_T.flac',
		]

	def test_case_only_differences_are_renames_not_new_folders(self) -> None:
		p = run({'a_burgh/Al/01_01_T.flac': tags(ALBUMARTIST='A_Burgh')})
		assert [(str(m.src), str(m.dst), m.case_only) for m in p.moves] == [
			('a_burgh/Al/01_01_T.flac', 'A_Burgh/Al/01_01_T.flac', True)
		]

	def test_the_first_spelling_of_a_folder_wins(self) -> None:
		p = run(
			{
				'a.flac': tags(ALBUMARTIST='Chris De Burgh', TITLE='A'),
				'b.flac': tags(ALBUMARTIST='Chris de Burgh', TITLE='B'),
			}
		)
		assert [str(m.dst) for m in p.moves] == ['Chris_De_Burgh/Al/01_01_A.flac']
		assert 'differently' in p.skipped[0].reason
		assert str(p.skipped[0].path) == 'b.flac'

	def test_two_files_with_the_same_name_do_not_both_move(self) -> None:
		p = run({'a.flac': tags(), 'b.flac': tags()})
		assert len(p.moves) == 1
		assert 'wanted by' in p.skipped[0].reason

	def test_unicode_forms_of_the_same_name_are_the_same_place(self) -> None:
		nfd = 'Café'  # e + combining acute
		p = run({f'{nfd}/Al/01_01_T.flac': tags(ALBUMARTIST='Café')})
		assert p.in_place + len(p.moves) == 1

	def test_the_plan_is_deterministic(self) -> None:
		files = {f'{c}.flac': tags(TITLE=c) for c in 'dcba'}
		assert [str(m.src) for m in run(files).moves] == ['a.flac', 'b.flac', 'c.flac', 'd.flac']

	def test_disc_dirs_are_found_from_paths(self) -> None:
		paths = [
			PurePosixPath('A/Al/Disc 1/x.flac'),
			PurePosixPath('A/Al/CD2/y.flac'),
			PurePosixPath('B/Bl/z.flac'),
		]
		assert planner.album_dirs_with_discs(paths) == {('A', 'Al')}


class TestMultiDisc:
	@pytest.mark.parametrize(
		('extra', 'multi'),
		[
			({}, False),
			({'DISCNUMBER': '2'}, True),
			({'DISCNUMBER': '1/2'}, True),
			({'DISCNUMBER': '1/1'}, False),
			({'DISCTOTAL': '3'}, True),
			({'TOTALDISCS': '2'}, True),
			({'DISCTOTAL': '1'}, False),
			({'DISCNUMBER': 'x'}, False),
		],
	)
	def test_detection(self, extra: dict[str, str], multi: bool) -> None:
		assert planner.is_multi_disc(tags(**extra)) is multi


class TestCustomTemplate:
	def custom(self) -> Template:
		return Template(
			folders=(
				(Chip('ALBUMARTIST'),),
				(Chip('DATE', fmt='year'), Chip(text=' - '), Chip('ALBUM')),
			),
			filename=(Chip('TRACKNUMBER', fmt='num', pad=3), Chip(text=' '), Chip('TITLE')),
		)

	def test_chips_literals_and_formats(self) -> None:
		p = run({'x.flac': tags(DATE='2020-05-06')}, self.custom())
		assert str(p.moves[0].dst) == 'A/2020 - Al/001 T.flac'

	def test_no_disc_folder_means_never_a_subfolder(self) -> None:
		p = run({'x.flac': tags(DATE='2020', DISCNUMBER='2')}, self.custom())
		assert str(p.moves[0].dst) == 'A/2020 - Al/001 T.flac'

	def test_a_fallback_chip_is_used_only_when_asked_for(self) -> None:
		t = Template(
			folders=((Chip('ALBUMARTIST', fallback='ARTIST'),), (Chip('ALBUM'),)),
			filename=(Chip('TITLE'),),
		)
		p = run({'x.flac': {**tags(ALBUMARTIST=''), 'ARTIST': 'Solo'}}, t)
		assert str(p.moves[0].dst) == 'Solo/Al/T.flac'

	def test_int_format_needs_a_number(self) -> None:
		t = Template(
			folders=((Chip('ALBUMARTIST'),),),
			filename=(Chip('DISCNUMBER', fmt='int'), Chip(text='-'), Chip('TITLE')),
		)
		assert str(run({'x.flac': tags(DISCNUMBER='02/3')}, t).moves[0].dst) == 'A/2-T.flac'
		assert run({'x.flac': tags(DISCNUMBER='x')}, t).unplaced

	def test_num_format_keeps_the_part_before_the_slash(self) -> None:
		t = Template(
			folders=((Chip('ALBUMARTIST'),),), filename=(Chip('TRACKNUMBER', fmt='num', pad=2),)
		)
		assert str(run({'x.flac': tags(TRACKNUMBER='3/12')}, t).moves[0].dst) == 'A/03.flac'


class TestValidate:
	def test_the_default_is_valid_without_warnings(self) -> None:
		assert template.validate(template.default()) == ([], [])

	def test_round_trip_through_json(self) -> None:
		t = template.default()
		assert Template.from_dict(json.loads(json.dumps(t.to_dict()))) == t

	@pytest.mark.parametrize(
		'bad',
		[
			Template(folders=(), filename=(Chip('TITLE'),)),
			Template(folders=((),), filename=(Chip('TITLE'),)),
			Template(folders=((Chip('NOPE'),),), filename=(Chip('TITLE'),)),
			Template(folders=((Chip(text='only text'),),), filename=(Chip('TITLE'),)),
			Template(folders=((Chip('ALBUM'),),), filename=(Chip(text='a/b'), Chip('TITLE'))),
			Template(folders=((Chip('ALBUM'),),), filename=(Chip('TITLE', fmt='weird'),)),
			Template(folders=((Chip('ALBUM', fallback='NOPE'),),), filename=(Chip('TITLE'),)),
			Template(folders=((Chip('ALBUM'),),) * 5, filename=(Chip('TITLE'),)),
			Template(
				folders=((Chip('ALBUM'),),), filename=(Chip('TRACKNUMBER', fmt='num', pad=9),)
			),
		],
	)
	def test_errors(self, bad: Template) -> None:
		assert template.validate(bad)[0]

	def test_warnings_for_names_that_can_collide(self) -> None:
		t = Template(folders=((Chip('ALBUM'),),), filename=(Chip('TITLE'),))
		warnings = template.validate(t)[1]
		assert any('same name' in w for w in warnings)
		assert any('multi-disc' in w for w in warnings)
