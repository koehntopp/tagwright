#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = ["mutagen", "pillow"]
# ///
"""Rewrite ARTIST and the credit tags from a fresh Discogs lookup, one value per name, and drop legacy tags (ADR 0100).

A one-off cleanup for albums assigned before ADR 0100: earlier taggers joined several names into one value
('Adele Adkins,Greg Kurstin') and left their own credit lists and junk tags. For every file with a
DISCOGS_RELEASE_ID this script looks the release up again and writes what an assignment now writes
(pipeline/credits.py):

- the credit tags (COMPOSER, LYRICIST, ARRANGER, CONDUCTOR, REMIXER, MIXER, PRODUCER, ENGINEER, PERSONNEL) from the
  track's credits; a credit tag Discogs has nothing for keeps its value, split at commas and semicolons;
- ARTIST as one value per track artist, when the file's ARTIST is the same artists in one joined value (an ARTIST
  that names someone else was set by hand and stays; it is reported);
- removes the legacy tags (credits.LEGACY_TAGS, credits.LEGACY_PREFIXES).

Safety: the file is matched to its release track by its Discogs position (TRACK_NUMBER_TEXT), else by
DISCOGS_RELEASE_ORDINAL_POSITION checked against that position; no match, an empty tracklist or a failed lookup skips the file or album. A file is never saved
when it would lose TITLE, ARTIST, ALBUM, ALBUMARTIST, TRACKNUMBER or DISCNUMBER. Dry run by default (a diff per
file); --write saves. Run it on a copy first (ADR 0018). The Discogs key comes from DISCOGS_API_KEY or the
settings file (--settings, default data/settings.json); Discogs allows about one release a second.
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from mutagen import MutagenError

# The pipeline package lives at the repository root, next to this scripts/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import credits, discogs  # noqa: E402  # after the path above
from pipeline.audio import is_audio, open_audio  # noqa: E402  # after the path above
from pipeline.fixtags import artist_names  # noqa: E402  # after the path above
from pipeline.http import ApiError  # noqa: E402  # after the path above
from pipeline.layout import album_root  # noqa: E402  # after the path above
from pipeline.tagio import touch, upper_tags  # noqa: E402  # after the path above

log = logging.getLogger('fix-credits')
SPLIT_KEYS = tuple(
	k for k, _, _ in credits.CREDIT_TAGS
)  # joined values of these are split without Discogs data


def albums(targets: list[Path]) -> dict[Path, list[Path]]:
	"""The audio files below the targets, grouped by album folder (a Disc N folder belongs to its parent)."""
	out: dict[Path, list[Path]] = {}
	for target in targets:
		for root, dirs, names in os.walk(target):
			dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
			for name in sorted(names):
				if is_audio(name) and not name.startswith('.'):
					out.setdefault(album_root(Path(root)), []).append(Path(root) / name)
	return dict(sorted(out.items()))


def same_artists(old: list[str], new: list[str]) -> bool:
	"""Whether the file's ARTIST names the same artists as Discogs, only joined differently."""
	if old == new:
		return True
	words = [
		p
		for v in old
		for p in re.split(r'\s*(?:,|;|&|/|\band\b|\bfeat\.?|\bfeaturing\b)\s*', v, flags=re.I)
	]
	return {w.strip().casefold() for w in words if w.strip()} == {n.casefold() for n in new}


def ordinal(tags: dict[str, list[str]], flat: list[tuple[dict, dict | None]]) -> int | None:
	"""The release track of a file: the one track whose position is TRACK_NUMBER_TEXT; else (positions repeat, or no
	TRACK_NUMBER_TEXT) DISCOGS_RELEASE_ORDINAL_POSITION when its track has that position. None when nothing matches.
	Positions come first because older writers counted headings in the ordinal."""
	text = (tags.get('TRACK_NUMBER_TEXT') or [''])[0].strip()
	hits = [i for i, (t, _) in enumerate(flat) if text and t.get('position', '') == text]
	if len(hits) == 1:
		return hits[0]
	raw = (tags.get('DISCOGS_RELEASE_ORDINAL_POSITION') or [''])[0].strip()
	if raw.isdigit() and int(raw) < len(flat):
		i = int(raw)
		return i if not text or flat[i][0].get('position', '') == text else None
	return None


def plan(tags: dict[str, list[str]], release: dict, i: int) -> tuple[dict, list[str], list[str]]:
	"""(tags to set, keys to delete, notes) for one file."""
	new = credits.track_tags(release, i)
	sets: dict[str, list[str]] = {}
	notes: list[str] = []
	for key in credits.CREDIT_KEYS:
		old = tags.get(key, [])
		value = new.get(key) or (credits.split_joined(old) if key in SPLIT_KEYS else old)
		if value and value != old:
			sets[key] = value
	if artists := new.get('ARTIST'):
		old = tags.get('ARTIST', [])
		entry, parent = credits.flat_tracks(release)[i]
		joined = artist_names(
			entry.get('artists') or (parent or {}).get('artists') or release.get('artists') or []
		)
		if old != artists and (old == [joined] or same_artists(old, artists)):
			sets['ARTIST'] = artists
		elif old != artists:
			notes.append(f'ARTIST {old} kept (Discogs: {artists})')
	return sets, credits.legacy_keys(list(tags)), notes


def fix_file(path: Path, release: dict, flat: list, write: bool) -> str:
	"""Plan and (with write) save one file. Returns 'changed', 'same' or 'skipped'."""
	audio = open_audio(path)
	before = upper_tags(audio)
	lacking = [k for k in credits.REQUIRED if not before.get(k)]
	if lacking:
		log.info('  %s: already lacks %s', path.name, ', '.join(lacking))
	i = ordinal(before, flat)
	if i is None:
		log.warning('  %s: skipped, no matching Discogs track', path.name)
		return 'skipped'
	sets, drops, notes = plan(before, release, i)
	for note in notes:
		log.info('  %s: %s', path.name, note)
	if not sets and not drops:
		return 'same'
	after = {k: v for k, v in before.items() if k not in {d.upper() for d in drops}} | sets
	if lost := credits.lost_required(before, after):
		log.warning('  %s: skipped, would lose %s', path.name, ', '.join(lost))
		return 'skipped'
	log.info('  %s', path.name)
	for k, v in sets.items():
		log.info('    %s: %s -> %s', k, before.get(k, []), v)
	if drops:
		log.info('    removed: %s', ', '.join(sorted(drops)))
	if write:
		for k in drops:
			del audio.tags[k]
		for k, v in sets.items():
			audio[k] = v
		audio.save()
		touch(path)
	return 'changed'


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument('paths', nargs='+', type=Path, help='library or album folders')
	parser.add_argument('--write', action='store_true', help='save the changes (default: dry run)')
	parser.add_argument(
		'--settings',
		type=Path,
		default=Path(__file__).resolve().parent.parent / 'data' / 'settings.json',
		help='Tagwright settings file with discogs_api_key (if DISCOGS_API_KEY is not set)',
	)
	args = parser.parse_args()
	logging.basicConfig(level=logging.INFO, format='%(message)s')
	key = os.environ.get('DISCOGS_API_KEY') or (
		json.loads(args.settings.read_text()).get('discogs_api_key', '')
		if args.settings.exists()
		else ''
	)
	if not key:
		parser.error('no Discogs key: set DISCOGS_API_KEY or pass --settings')
	discogs.configure(lambda: key)

	counts = {'changed': 0, 'same': 0, 'skipped': 0, 'errors': 0}
	for album, files in albums(args.paths).items():
		log.info('%s', album)
		cache: dict[str, dict | None] = {}  # per album: one lookup per release
		for path in files:
			try:
				rid = (upper_tags(open_audio(path)).get('DISCOGS_RELEASE_ID') or [''])[0].strip()
				if not rid.isdigit():
					log.warning('  %s: skipped, no DISCOGS_RELEASE_ID', path.name)
					counts['skipped'] += 1
					continue
				if rid not in cache:
					try:
						cache[rid] = discogs.get(f'/releases/{rid}')
					except ApiError as e:
						log.error('  release %s: %s', rid, e)
						cache[rid] = None
				release = cache[rid]
				flat = credits.flat_tracks(release) if release else []
				if not flat:
					log.warning('  %s: skipped, release %s has no tracks', path.name, rid)
					counts['skipped'] += 1
					continue
				counts[fix_file(path, release, flat, args.write)] += 1
			except (MutagenError, OSError, ValueError) as e:
				log.error('  %s: %s', path.name, e)
				counts['errors'] += 1
	log.info(
		'%s: %d changed, %d unchanged, %d skipped, %d error(s)',
		'wrote' if args.write else 'dry run',
		counts['changed'],
		counts['same'],
		counts['skipped'],
		counts['errors'],
	)


if __name__ == '__main__':
	main()
