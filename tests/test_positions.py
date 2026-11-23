"""Disc and track numbers from Discogs positions (ADR 0053, 0101)."""

import pytest

import app as tagwright
from pipeline.positions import Positions


def placed(items: list[str]) -> list[tuple[int, int] | None]:
	"""Positions in tracklist order; an item starting with '#' is a heading."""
	p, out = Positions(), []
	for item in items:
		if item.startswith('#'):
			p.heading(item[1:])
		else:
			out.append(p.place(item))
	return out


@pytest.mark.parametrize(
	('items', 'want'),
	[
		(['1-1', '2.3', 'CD2-4', 'DVD1-1'], [(1, 1), (2, 3), (2, 4), (1, 1)]),
		(['SACD1-4', 'BD2-1', 'HDCD1-3'], [(1, 4), (2, 1), (1, 3)]),
		# a label without a disc number: every new label is the next disc
		(['SACD-1', 'SACD-2', 'CD-1', 'DVD-1', 'CD-2'], [(1, 1), (1, 2), (2, 1), (3, 1), (2, 2)]),
		# after numbered discs the next label continues the count
		(['CD1-1', 'CD2-1', 'DVD-1'], [(1, 1), (2, 1), (3, 1)]),
		# a 'Disc N' heading decides, also for the same label on two discs
		(['#Disc 1', 'CD-1', '#Disc 2', 'CD-1'], [(1, 1), (2, 1)]),
		(['#SACD 1', '1', '2', '#Blu-ray 2', '1'], [(1, 1), (1, 2), (2, 1)]),
		# vinyl sides, plain numbers without a heading and empty positions name no disc
		(['A1', 'B2', '1', '', 'A1.1'], [None, None, None, None, None]),
	],
)
def test_positions(items: list[str], want: list[tuple[int, int] | None]) -> None:
	assert placed(items) == want


def test_a_sacd_cd_dvd_set_gets_three_discs(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Billy Joel, Piano Man (Discogs 29934862): SACD-n, CD-n and DVD-n under 'Disc N (format)' headings; before,
	every track was on disc 1, numbered 1..n through the whole release."""
	raw = {
		'id': 7,
		'title': 'Piano Man',
		'artists': [{'name': 'Billy Joel'}],
		'tracklist': [
			{'type_': 'heading', 'title': 'Disc 1 (SA-CD): Piano Man (The Original Album)'},
			{'type_': 'track', 'position': 'SACD-1', 'title': "Travelin' Prayer"},
			{'type_': 'track', 'position': 'SACD-2', 'title': 'Piano Man'},
			{'type_': 'heading', 'title': 'Disc 2 (CD): Rare Live & Demo Tracks'},
			{'type_': 'track', 'position': 'CD-1', 'title': 'Piano Man (Single Edit)'},
			{'type_': 'heading', 'title': 'Disc 3 (DVD): Rare Videos'},
			{'type_': 'track', 'position': 'DVD-1', 'title': 'Piano Man (1974 Video)'},
		],
	}
	monkeypatch.setattr(tagwright, 'discogs', lambda path, **kw: raw)
	tagwright.releases.pop('7', None)
	got = [(t['disc'], t['track']) for t in tagwright.release_tracks('7')['tracks']]
	assert got == [(1, 1), (1, 2), (2, 1), (3, 1)]
