"""LYRICS_LANGUAGE from MusicBrainz, anchored by the user-set MUSICBRAINZ_ALBUMID (ADR 0023, 0036)."""

import logging

from pipeline import musicbrainz
from pipeline.audio import Audio
from pipeline.config import Config

log = logging.getLogger(__name__)

LANGUAGE_TAG = 'LYRICS_LANGUAGE'


def release_id(tags: dict[str, list[str]]) -> str:
	"""The user-set MusicBrainz release id (not the release-group id) from upper-cased tags."""
	for key in ('MUSICBRAINZ_ALBUMID', 'MUSICBRAINZ ALBUM ID'):
		values = tags.get(key)
		if values and values[0].strip():
			return values[0].strip()
	return ''


def load_release(
	first_tags: dict[str, list[str]], cfg: Config, refresh: bool = False
) -> dict | None:
	"""The album's parsed MusicBrainz release, or None: switched off, no MUSICBRAINZ_ALBUMID, or MusicBrainz
	could not be asked (then language tags stay as they are)."""
	if not cfg.musicbrainz_languages:
		return None
	mbid = release_id(first_tags)
	if not mbid:
		return None
	release = musicbrainz.release_languages(mbid, cfg.data_dir / 'musicbrainz', refresh)
	if release is None:
		log.warning(
			'MusicBrainz lookup failed for release %s; %s left as it is', mbid, LANGUAGE_TAG
		)
	return release


def _leading_int(value: str, default: int) -> int:
	try:
		return int(value.split('/')[0].strip())
	except ValueError:
		return default


def apply_language(audio: Audio, release: dict | None) -> bool:
	"""Set (or remove) LYRICS_LANGUAGE on one file from the MusicBrainz release; True if it changed.

	A file that cannot be matched to a MusicBrainz track (another edition of the album) keeps whatever
	it has; a matched track with no sung language loses the tool-owned tag.
	"""
	if release is None or audio.tags is None:
		return False
	tags = audio.tags
	track = musicbrainz.find_track(
		release,
		tags.get('MUSICBRAINZ_RELEASETRACKID', [''])[0].strip(),
		_leading_int(tags.get('DISCNUMBER', ['1'])[0], 1),
		_leading_int(tags.get('TRACKNUMBER', ['0'])[0], 0),
		tags.get('TITLE', [''])[0],
	)
	if track is None:
		return False
	wanted = track['languages']
	if [str(x) for x in tags.get(LANGUAGE_TAG, [])] == wanted:
		return False
	if wanted:
		audio[LANGUAGE_TAG] = wanted
	elif LANGUAGE_TAG in tags:
		del tags[LANGUAGE_TAG]
	else:
		return False
	return True
