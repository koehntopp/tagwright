"""Fix tags from the Discogs release (ADR 0013, 0014, 0036): the tags the owner's tagger no longer writes.

Reads DISCOGS_RELEASE_ID from the first FLAC of an album, asks Discogs for the release (and its master),
and rewrites every file of the album with one consistent set of tags. This is the discogs `fixtags.py`,
reduced to what Tagwright needs: no command line, no Discogs client library, no config module; the Discogs
data comes in through the `get` argument so the logic is testable without a network.

Tags written uniformly to every file:

	RELEASEDATE / DATE / YEAR              release year of this pressing
	ORIGINALDATE / ORIGINALRELEASEDATE / ORIGINAL DATE / ORIGINAL YEAR   year of the master release
	ALBUM                                  ALBUM_TITLE_OVERRIDE, else the master title, else the release title
	VERSION                                "<year> DR<dr> <format> (<edition>) (<catalog number>)"
	ORIGINAL_TITLE, ALBUM_MASTER_TITLE, ALBUM_RELEASE_TITLE, ALBUM_MASTER_YEAR, ALBUM_FORMAT,
	ALBUM_MAX_RESOLUTION, and when they have a value ALBUM_RELEASE_YEAR, ALBUM_EDITION, ALBUM_DR,
	ALBUM_RELEASE_COUNTRY, ALBUM_RELEASE_LABEL, ALBUM_COMPANY_*, ALBUM_CREDIT_*, ALBUM_IDENT_*,
	ALBUM_RELEASE_* (see `discogs_extra_tags`)
	ALBUMARTIST                            only with ALBUM_ARTIST_OVERRIDE (a manual correction), else untouched

Per track: DISCSUBTITLE from the track's own SET SUBTITLE, LYRICS_LANGUAGE from MusicBrainz. Tags that no
longer have a value on Discogs are removed; the legacy WORK and PART grouping tags are removed.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mutagen import MutagenError
from mutagen.flac import FLAC

from pipeline import covers, discogs, languages
from pipeline.config import Config
from pipeline.http import ApiError
from pipeline.layout import flacs
from pipeline.tagio import touch, upper_tags

log = logging.getLogger(__name__)

# Tag families written from the Discogs release; keys vary per release, so stale ones are swept by prefix.
DISCOGS_TAG_PREFIXES = ('ALBUM_COMPANY_', 'ALBUM_CREDIT_', 'ALBUM_IDENT_')
# Fixed-name tags from discogs_extra_tags, removed from files when Discogs no longer has a value.
DISCOGS_EXTRA_FIXED = (
	'ALBUM_RELEASE_LABELS',
	'ALBUM_RELEASE_CATALOGNUMBERS',
	'ALBUM_RELEASE_FORMAT',
	'ALBUM_RELEASE_FORMAT_DESCRIPTIONS',
	'ALBUM_RELEASE_FORMAT_TEXT',
	'ALBUM_RELEASE_GENRES',
	'ALBUM_RELEASE_STYLES',
	'ALBUM_RELEASE_NOTES',
	'ALBUM_RELEASE_DATE_FULL',
	'ALBUM_RELEASE_DATA_QUALITY',
	'ALBUM_RELEASE_SERIES',
)
# Optional tags this step owns: written when there is a value, removed when there is none.
MANAGED_OPTIONAL = (
	'ALBUM_EDITION',
	'ALBUM_DR',
	'ALBUM_RELEASE_YEAR',
	'ALBUM_RELEASE_COUNTRY',
	'ALBUM_RELEASE_LABEL',
)
LEGACY_GROUPING = ('WORK', 'PART')  # replaced by DISCSUBTITLE
CATALOG_SPELLINGS = ('CATALOGNUMBER', 'CATALOG NUMBER', 'CATALOG_NUMBER', 'CATALOGNO')

type Get = Callable[..., dict]  # get(path) -> Discogs JSON; discogs.get in production


def tag_key(prefix: str, text: str) -> str:
	"""'Glass Mastered At' -> '<prefix>GLASS_MASTERED_AT' (an empty string if nothing usable is left)."""
	slug = re.sub(r'[^A-Z0-9]+', '_', text.upper()).strip('_')
	return f'{prefix}{slug}' if slug else ''


def clean_name(name: str) -> str:
	"""Drop Discogs' ' (2)' artist disambiguation suffix."""
	return re.sub(r'\s*\(\d+\)$', '', name.strip())


def discogs_extra_tags(data: dict) -> dict[str, list[str]]:
	"""Map a raw Discogs release to quality-relevant, album-level tags.

	ALBUM_COMPANY_<ROLE>  companies (Mastered At, Pressed By, Glass Mastered At, ...)
	ALBUM_CREDIT_<ROLE>   extraartists ("Mastered By [detail]" -> value "Name [detail]")
	ALBUM_IDENT_<TYPE>    identifiers (Matrix / Runout, Barcode, Mastering SID Code, ...)
	plus labels, catalogue numbers, format, genres, styles, series, notes, full date, data quality.
	Empty values are omitted. The order of first appearance is kept, duplicates are dropped.
	"""
	tags: dict[str, list[str]] = {}

	def add(key: str, value: str) -> None:
		value = (value or '').strip()
		if key and value and value not in tags.setdefault(key, []):
			tags[key].append(value)

	for c in data.get('companies') or []:
		add(tag_key('ALBUM_COMPANY_', c.get('entity_type_name', '')), clean_name(c.get('name', '')))

	for a in data.get('extraartists') or []:
		role = a.get('role', '')
		detail = re.search(r'\[(.*)\]', role)
		base = re.sub(r'\s*\[.*?\]', '', role)
		name = clean_name(a.get('name', ''))
		value = f'{name} [{detail.group(1)}]' if detail and name else name
		# "Producer, Engineer" credits the same person under both roles
		for r in base.split(','):
			add(tag_key('ALBUM_CREDIT_', r), value)

	for i in data.get('identifiers') or []:
		desc = (i.get('description') or '').strip()
		val = (i.get('value') or '').strip()
		add(tag_key('ALBUM_IDENT_', i.get('type', '')), f'{val} ({desc})' if desc and val else val)

	for lab in data.get('labels') or []:
		add('ALBUM_RELEASE_LABELS', clean_name(lab.get('name', '')))
		cat = (lab.get('catno') or '').strip()
		if cat.lower() != 'none':
			add('ALBUM_RELEASE_CATALOGNUMBERS', cat)

	for f in data.get('formats') or []:
		add('ALBUM_RELEASE_FORMAT', f.get('name', ''))
		for d in f.get('descriptions') or []:
			add('ALBUM_RELEASE_FORMAT_DESCRIPTIONS', d)
		add('ALBUM_RELEASE_FORMAT_TEXT', f.get('text', ''))

	for g in data.get('genres') or []:
		add('ALBUM_RELEASE_GENRES', g)
	for s in data.get('styles') or []:
		add('ALBUM_RELEASE_STYLES', s)
	for s in data.get('series') or []:
		add('ALBUM_RELEASE_SERIES', s.get('name', ''))

	add('ALBUM_RELEASE_NOTES', data.get('notes', ''))
	add('ALBUM_RELEASE_DATE_FULL', data.get('released', ''))
	add('ALBUM_RELEASE_DATA_QUALITY', data.get('data_quality', ''))
	return tags


def max_resolution(max_rate_hz: int) -> str:
	"""ALBUM_MAX_RESOLUTION: '44.1kHz', '96kHz', '176.4kHz'; 44.1kHz when no rate is known."""
	if max_rate_hz <= 0:
		return '44.1kHz'
	return f'{max_rate_hz / 1000:.1f}kHz'.replace('.0kHz', 'kHz')


def version_string(year: int, dr: str, album_format: str, edition: str, catalog_number: str) -> str:
	"""'2020 DR07 CD (Deluxe) (CAT-1)': year, DR, format, edition, catalog number; missing parts are left out."""
	dr_str = ''
	if dr:
		try:
			dr_str = f'DR{int(dr):02d}'
		except ValueError:
			dr_str = ''
	yr_str = f'{year}' if year else ''
	dr_part = f' {dr_str}' if dr_str else ''
	fmt_part = f' {album_format}' if album_format else ''
	ed_part = f' ({edition})' if edition else ''
	cat_part = f' ({catalog_number})' if catalog_number else ''
	return f'{yr_str}{dr_part}{fmt_part}{ed_part}{cat_part}'.strip()


def first_value(tags: dict[str, list[str]], *keys: str) -> str:
	"""The first non-empty value of the keys, in order ('' if none; a key with an empty list is skipped)."""
	for key in keys:
		values = tags.get(key)
		if values and values[0]:
			return values[0]
	return ''


def fetch_master(get: Get, release: dict) -> tuple[dict | None, str]:
	"""(master release or None, master title). Without a master, or when it cannot be had, the release title."""
	title = release['title'].strip()
	if not release.get('master_id'):
		return None, title
	try:
		master = get(f'/masters/{release["master_id"]}')
		return master, master['title'].strip()
	except ApiError, KeyError, AttributeError, TypeError:
		return None, title


def master_year(get: Get, master: dict | None, release_year: int, discogs_id: int) -> int:
	"""Year of the master's main release; the release year without a master or when it cannot be had."""
	if master is None:
		return release_year
	try:
		return int(get(f'/releases/{master["main_release"]}').get('year') or 0)
	except ApiError, KeyError, AttributeError, TypeError, ValueError:
		log.warning(
			'Could not fetch master release year for Discogs ID %s, using release year', discogs_id
		)
		return release_year


@dataclass
class Plan:
	"""What every file of the album should carry."""

	tags: dict[str, list[str]]
	album_name: str
	version: str


def plan_tags(
	first_tags: dict[str, list[str]],
	release: dict,
	master: dict | None,
	master_title: str,
	year_master: int,
	max_rate_hz: int,
) -> Plan:
	"""The album-level tags from the first file's tags (upper-cased keys) and the Discogs data."""
	release_title = release['title'].strip()
	album_name = first_value(first_tags, 'ALBUM_TITLE_OVERRIDE') or master_title
	# ALBUM_ARTIST_OVERRIDE only ever corrects a wrong ALBUMARTIST manually; absent, ALBUMARTIST is left alone.
	artist_override = first_value(first_tags, 'ALBUM_ARTIST_OVERRIDE').strip()

	# Tool-written tags are never read back as input: the release year comes only from the Discogs release.
	release_year = int(release.get('year') or 0)
	year_release = release_year
	if year_release == 0 and year_master != 0:
		year_release = year_master
	if year_release != 0 and year_master == 0:
		year_master = year_release

	subtitle = first_value(first_tags, 'SUBTITLE').strip()
	album_format = first_value(first_tags, 'ALBUM_FORMAT') or subtitle or 'CD'
	edition = first_value(first_tags, 'ALBUM_EDITION')
	dr_rating = first_value(first_tags, 'ALBUM_DR')
	catalog = first_value(first_tags, *CATALOG_SPELLINGS).strip()
	version = version_string(year_release, dr_rating, album_format, edition, catalog)

	tags: dict[str, list[str]] = {
		'RELEASEDATE': [str(year_release)],
		'DATE': [str(year_release)],
		'YEAR': [str(year_release)],
		'ORIGINALDATE': [str(year_master)],
		'ORIGINALRELEASEDATE': [str(year_master)],
		'ORIGINAL DATE': [str(year_master)],
		'ORIGINAL YEAR': [str(year_master)],
		'ALBUM_MASTER_TITLE': [master_title],
		'ALBUM_RELEASE_TITLE': [release_title],
		'ALBUM_MASTER_YEAR': [str(year_master)],
		'ALBUM_FORMAT': [album_format],
		'ALBUM_MAX_RESOLUTION': [max_resolution(max_rate_hz)],
		'ALBUM': [album_name],
		'VERSION': [version],
		'ORIGINAL_TITLE': [master_title],
	}
	if release_year:
		tags['ALBUM_RELEASE_YEAR'] = [str(release_year)]
	if edition:
		tags['ALBUM_EDITION'] = [edition]
	if dr_rating:
		tags['ALBUM_DR'] = [dr_rating]
	if artist_override:
		tags['ALBUMARTIST'] = [artist_override]

	country = (release.get('country') or '').strip()
	if country:
		tags['ALBUM_RELEASE_COUNTRY'] = [country]
	label = ((release.get('labels') or [{}])[0].get('name') or '').strip()
	if label:
		tags['ALBUM_RELEASE_LABEL'] = [label]

	# Everything else Discogs knows about this pressing (companies, credits, identifiers, format, notes ...).
	try:
		tags.update(discogs_extra_tags(release))
	except (AttributeError, TypeError, KeyError) as e:
		log.warning('Could not map extra Discogs fields for %s: %s', release.get('id'), e)
	return Plan(tags=tags, album_name=album_name, version=version)


def stale_tags(audio: FLAC, plan: Plan) -> list[str]:
	"""Tags of a file that this step owns but no longer has a value for."""
	return [
		key
		for key in [
			*MANAGED_OPTIONAL,
			*DISCOGS_EXTRA_FIXED,
			*(k for k in audio.tags.keys() if k.upper().startswith(DISCOGS_TAG_PREFIXES)),
		]
		if key.upper() not in plan.tags and key in audio.tags  # mutagen returns keys lower-cased
	]


def update_file(path: Path, plan: Plan, mb_release: dict | None) -> bool:
	"""Bring one file in line with the plan; True when it was rewritten."""
	audio = FLAC(path)
	if audio.tags is None:  # an existing but empty Vorbis comment is fine; add_tags() would raise
		audio.add_tags()

	# DISCSUBTITLE is per track (Roon box-set disc title): each track's own SET SUBTITLE, a tag the user sets
	# on the discs of multi-disc editions, so it varies from track to track inside one album.
	set_subtitle = audio.tags.get('SET SUBTITLE', [''])[0].strip()
	subtitle_changed = bool(set_subtitle) and [
		str(x) for x in audio.tags.get('DISCSUBTITLE', [])
	] != [set_subtitle]
	subtitle_stale = not set_subtitle and 'DISCSUBTITLE' in audio.tags
	legacy = [t for t in LEGACY_GROUPING if t in audio.tags]

	language_changed = languages.apply_language(audio, mb_release)
	stale = stale_tags(audio, plan)
	for key in stale:
		del audio.tags[key]
	needs_update = (
		bool(stale)
		or bool(legacy)
		or subtitle_stale
		or language_changed
		or subtitle_changed
		or any([str(x) for x in audio.tags.get(k, [])] != v for k, v in plan.tags.items())
	)
	if not needs_update:
		return False

	for k, v in plan.tags.items():
		audio[k] = v
	for key in legacy:
		del audio.tags[key]
	if set_subtitle:
		audio['DISCSUBTITLE'] = [set_subtitle]
	elif 'DISCSUBTITLE' in audio.tags:
		del audio.tags['DISCSUBTITLE']
	audio.save()
	touch(path)
	return True


@dataclass
class FixResult:
	changed: int  # files rewritten
	album_name: str = ''
	version: str = ''
	skipped: str = ''  # why nothing was done ('' = the album was processed)


def fix_album(
	album: Path, cfg: Config, get: Get = discogs.get, refresh_musicbrainz: bool = False
) -> FixResult:
	"""Enrich all FLAC files of one album with Discogs metadata.

	Skips the album (silently, as a result with `skipped`) when it has no FLAC files, the first file is
	unreadable, or DISCOGS_RELEASE_ID is missing or not a number. A Discogs failure raises ApiError.
	"""
	files = flacs(album)
	if not files:
		return FixResult(0, skipped='no flac files')
	try:
		first = FLAC(files[0])
		first_tags = upper_tags(first)
		first_rate = first.info.sample_rate if first.info else 44100
	except (MutagenError, OSError) as e:
		log.warning('Skipping unreadable file %s: %s', files[0], e)
		return FixResult(0, skipped='unreadable first file')
	try:
		discogs_id = int(first_tags.get('DISCOGS_RELEASE_ID', [''])[0])
	except ValueError, IndexError:
		return FixResult(0, skipped='no Discogs release ID')

	release = get(f'/releases/{discogs_id}')
	master, master_title = fetch_master(get, release)
	year_master = master_year(get, master, int(release.get('year') or 0), discogs_id)

	def rate(path: Path) -> int:
		try:
			return FLAC(path).info.sample_rate
		except MutagenError, OSError, AttributeError:
			return 0

	max_rate = max((rate(p) for p in files), default=first_rate)
	plan = plan_tags(first_tags, release, master, master_title, year_master, max_rate)
	mb_release = languages.load_release(first_tags, cfg, refresh_musicbrainz)

	changed = 0
	for path in files:
		if not path.is_file():
			continue
		try:
			if update_file(path, plan, mb_release):
				changed += 1
		except (MutagenError, OSError) as e:
			log.warning('Skipping unreadable or unwritable file %s: %s', path, e)

	title = f'{plan.album_name} [{plan.version}]' if plan.version else plan.album_name
	if changed == 0:
		log.info('No changes required for %s', title)
	elif first_value(first_tags, 'ALBUM') != plan.album_name:
		log.info('Album name changed to %s', title)
	else:
		log.info('Tags updated in %s', title)
	covers.resize_covers(album, cfg.cover_max_size)
	return FixResult(changed, plan.album_name, plan.version)
