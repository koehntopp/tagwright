"""The tag lists of the web layer and the Discogs tags step stay in line (ADR 0014, 0036)."""

import app as tagwright
from pipeline import fixtags

RICH = {
	'id': 1,
	'title': 'T',
	'year': 2020,
	'country': 'UK',
	'labels': [{'name': 'L', 'catno': 'C'}],
	'formats': [{'name': 'CD', 'descriptions': ['Album'], 'text': 't'}],
	'genres': ['Rock'],
	'styles': ['Indie'],
	'series': [{'name': 'S'}],
	'notes': 'n',
	'released': '2020-01-01',
	'data_quality': 'Correct',
	'companies': [{'entity_type_name': 'Pressed By', 'name': 'MPO'}],
	'extraartists': [{'name': 'Bob', 'role': 'Producer'}],
	'identifiers': [{'type': 'Barcode', 'value': '1'}],
}
USER_OWNED = {
	'ALBUM_FORMAT',
	'ALBUM_EDITION',
	'ALBUMARTIST',
}  # editable; the step only reads or copies them


def test_every_tag_the_step_writes_is_shown_read_only_by_the_tag_editor() -> None:
	first = {'ALBUM_DR': ['07'], 'ALBUM_EDITION': ['Deluxe'], 'ALBUM_ARTIST_OVERRIDE': ['X']}
	written = set(fixtags.plan_tags(first, RICH, {}, 'Master', 2001, 96000).tags)
	families = tuple(fixtags.DISCOGS_TAG_PREFIXES)
	fixed = {k for k in written if not k.startswith(families)} - USER_OWNED
	assert fixed == set(tagwright.DISCOGS_FIXED)


def test_the_stale_sweep_covers_the_fixed_extra_tags() -> None:
	assert set(fixtags.DISCOGS_EXTRA_FIXED) <= set(tagwright.DISCOGS_FIXED)


def test_the_prefix_families_are_the_same() -> None:
	assert set(fixtags.DISCOGS_TAG_PREFIXES) <= set(tagwright.DISCOGS_PREFIXES)


def test_the_tag_editor_never_offers_a_discogs_owned_tag_as_editable() -> None:
	assert not set(tagwright.ALBUM_FIELDS) & set(tagwright.DISCOGS_FIXED)
