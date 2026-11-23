"""Track artists and credits from a Discogs release, the legacy tags they replace, and the required-tags guard (ADR 0100).

Every credit is one value per person, as Roon reads them: the dedicated tags below for the roles Roon has a tag for,
`PERSONNEL` (`Name - Role`) for every other role. A track's credits are its own (and, for a part of a medley, those of
the whole entry) plus the release credits whose `tracks` range covers it; a dedicated tag with nothing from those
falls back to the release-wide credits (no range), as the assignment did before. `PERSONNEL` always includes them.
"""

import re
from collections.abc import Iterable

# Dedicated credit tags and the Discogs role words (lower case, qualifier in brackets removed) that fill them.
# A role matches the first tag whose words it equals or, for the `in` entries, contains.
CREDIT_TAGS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
	# (tag, exact roles, roles containing)
	('COMPOSER', ('written-by', 'written by', 'composed by', 'music by', 'songwriter'), ()),
	('LYRICIST', ('lyrics by', 'words by'), ()),
	('ARRANGER', (), ('arranged by',)),
	('CONDUCTOR', ('conductor',), ()),
	('REMIXER', (), ('remix',)),
	('MIXER', ('mixed by',), ()),
	('PRODUCER', (), ('producer',)),
	('ENGINEER', ('recorded by',), ('engineer',)),
)
CREDIT_KEYS = (*(t for t, _, _ in CREDIT_TAGS), 'PERSONNEL')
# Discogs '... By' roles under the noun Roon lists; any other 'X By' becomes 'X' (Photography By -> Photography).
PERSONNEL_ROLES = {
	'mastered by': 'Mastering Engineer',
	'remastered by': 'Remastering Engineer',
	'programmed by': 'Programming',
	'edited by': 'Editing',
	'directed by': 'Director',
	'orchestrated by': 'Orchestration',
	'transferred by': 'Transfer',
	'translated by': 'Translation',
}


def personnel_role(role: str) -> str:
	"""The role as written in PERSONNEL."""
	return PERSONNEL_ROLES.get(role.lower()) or re.sub(r'\s+By$', '', role, flags=re.I)


# Tags an earlier tagger or ripper wrote that Tagwright replaces or never uses; removed when credits are written.
LEGACY_TAGS = frozenset(
	{
		'PERFORMER',  # 'Name (Role)': replaced by PERSONNEL
		'PERFORMERYR',
		'INVOLVEDPEOPLE',
		'INVOLVEDPEOPLEYR',
		'RETAIL DATE',
		'RIP DATE',
		'RELEASE TYPE',
		'ORGANIZATION',
		'DYNAMIC RANGE (DR)',
		'DYNAMIC RANGE (R128)',
		'ALBUM DYNAMIC RANGE (DR)',
		'ALBUM DYNAMIC RANGE (R128)',
		'ORIGINALYEAR',
		'TRACKNUM',
		'DISC',
		'TRACK',
		'ALBUMARTIST2',
		'ARTISTS',
		'NUMBER_OF_FRAMES',
		'NUMBER_OF_BYTES',
		'BPS',
		'DURATION',
		'LENGTH',
		'APISEEDS_STATUS',
		'GET_LYRICS_STATUS',
	}
)
# 'DISCOGS ' with a space: the old tagger's copies of Discogs data (Tagwright writes DISCOGS_); ffmpeg statistics.
LEGACY_PREFIXES = ('DISCOGS ', '_STATISTICS_')

# A file must keep these; an update that would take one away is not saved.
REQUIRED = ('TITLE', 'ARTIST', 'ALBUM', 'ALBUMARTIST', 'TRACKNUMBER', 'DISCNUMBER')


def clean_artist(name: str) -> str:
	"""A Discogs name without its ' (2)' disambiguation suffix."""
	return re.sub(r'\s*\(\d+\)$', '', name.strip())


def uniq(xs: Iterable[str | None]) -> list[str]:
	return list(dict.fromkeys(x for x in xs if x))


def flat_tracks(release: dict) -> list[tuple[dict, dict | None]]:
	"""The release tracks in assignment order (`DISCOGS_RELEASE_ORDINAL_POSITION`): (entry, parent).

	A medley or work in parts (an index entry with sub-tracks) is its entry followed by its parts, each part with
	the entry as parent; headings and other entries are skipped (ADR 0046, 0060).
	"""
	out: list[tuple[dict, dict | None]] = []
	for t in release.get('tracklist') or []:
		parts = t.get('sub_tracks') or [] if t.get('type_') == 'index' else []
		if parts:
			out.append((t, None))
			out += [(p, t) for p in parts]
		elif t.get('type_') == 'track':
			out.append((t, None))
	return out


def _covered(spec: str, position: str, order: list[str]) -> bool:
	"""Whether a credit's `tracks` text ('1 to 3, 5', 'A1 to B2') covers the position."""
	if position not in order:
		return False
	at = order.index(position)
	for part in spec.split(','):
		ends = [s.strip() for s in re.split(r'\s+to\s+', part.strip(), flags=re.I)]
		if len(ends) == 2 and ends[0] in order and ends[1] in order:
			if order.index(ends[0]) <= at <= order.index(ends[1]):
				return True
		elif ends[0] == position:
			return True
	return False


def _roles(role: str) -> list[str]:
	"""The roles of one credit ('Bass, Producer [Additional]'), each without its bracketed qualifier."""
	parts = re.split(r',\s*(?![^\[]*\])', role or '')
	return [r for p in parts if (r := re.sub(r'\s*\[.*?\]', '', p).strip())]


def _tag_of(role: str) -> str:
	low = role.lower()
	for key, exact, contains in CREDIT_TAGS:
		if low in exact or any(w in low for w in contains):
			return key
	return 'PERSONNEL'


def _collect(credits: list[dict]) -> dict[str, list[str]]:
	out: dict[str, list[str]] = {}
	for c in credits:
		name = clean_artist(c.get('name', ''))
		if not name:
			continue
		for role in _roles(c.get('role', '')):
			key = _tag_of(role)
			value = f'{name} - {personnel_role(role)}' if key == 'PERSONNEL' else name
			out.setdefault(key, []).append(value)
	return {k: uniq(v) for k, v in out.items()}


def track_tags(release: dict, ordinal: int) -> dict[str, list[str]]:
	"""ARTIST and the credit tags of the release track at `ordinal`, one value per name; tags without a value are
	left out ({} when there is no such track)."""
	flat = flat_tracks(release)
	if not 0 <= ordinal < len(flat):
		return {}
	entry, parent = flat[ordinal]
	order = [t.get('position', '') for t, _ in flat]
	positions = {entry.get('position', ''), (parent or {}).get('position', '')} - {''}
	release_credits = release.get('extraartists') or []
	own = _collect(
		[*(entry.get('extraartists') or []), *((parent or {}).get('extraartists') or [])]
		+ [
			c
			for c in release_credits
			if (c.get('tracks') or '').strip()
			and any(_covered(c['tracks'], p, order) for p in positions)
		]
	)
	wide = _collect([c for c in release_credits if not (c.get('tracks') or '').strip()])
	out = {k: own.get(k) or wide.get(k, []) for k in CREDIT_KEYS}
	out['PERSONNEL'] = uniq([*own.get('PERSONNEL', []), *wide.get('PERSONNEL', [])])
	artists = entry.get('artists') or (parent or {}).get('artists') or release.get('artists') or []
	out['ARTIST'] = uniq([clean_artist(a.get('name', '')) for a in artists])
	return {k: v for k, v in out.items() if v}


def split_joined(values: list[str]) -> list[str]:
	"""One value per name for a credit an earlier tagger joined with commas or semicolons ('A,B' -> ['A', 'B'])."""
	if len(values) != 1:
		return values
	return uniq([p.strip() for p in re.split(r'\s*[,;]\s*', values[0])])


def legacy_keys(keys: list[str]) -> list[str]:
	"""The keys among `keys` that are legacy tags."""
	return [k for k in keys if k.upper() in LEGACY_TAGS or k.upper().startswith(LEGACY_PREFIXES)]


def lost_required(before: dict[str, list[str]], after: dict[str, list[str]]) -> list[str]:
	"""Required tags that had a value before and have none after (upper-case keys)."""
	return [
		k
		for k in REQUIRED
		if any(x.strip() for x in before.get(k, []))
		and not any(x.strip() for x in after.get(k, []))
	]
