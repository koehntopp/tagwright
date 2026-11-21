#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = ["mutagen", "pillow"]
# ///
"""Retype a single untyped embedded picture to Front Cover (type 3).

A one-off correction for libraries whose FLAC/MP3 files carry the cover as an untyped picture. ADR 0016 already
treats such a picture as the front cover; this writes the type so the four cover fields of ADR 0090 see it too.

Dry-run by default. Pass --write to save. Only files with exactly one picture are touched; files with several
pictures, and pictures already typed 3, are left alone. Per-file output is limited to files with more than one
picture (plus errors); the summary counts the other reasons. Never run --write on a test or scratch library that
matters, and verify on a copy first (ADR 0018).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from mutagen import MutagenError

# The pipeline package lives at the repository root, next to this scripts/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.audio import is_audio, open_audio  # noqa: E402  # after the path above

log = logging.getLogger('retype-covers')


def audio_files(target: Path) -> list[Path]:
	"""The audio files at a path, recursively for a folder; hidden entries are skipped."""
	if target.is_file():
		return [target] if is_audio(target.name) else []
	found: list[Path] = []
	for root, dirs, names in os.walk(target):
		dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
		found += [
			Path(root) / name for name in names if is_audio(name) and not name.startswith('.')
		]
	return sorted(found)


def retype(path: Path, write: bool) -> tuple[str, str]:
	"""Retype the one picture of a file to 3. Returns (reason, detail) for the summary and the multi-image line."""
	audio = open_audio(path)
	pictures = audio.pictures
	if len(pictures) > 1:
		return 'multi', f'{len(pictures)} pictures'
	if not pictures:
		return 'empty', ''
	pic = pictures[0]
	if pic.type == 3:
		return 'front', ''
	if write:
		audio.clear_pictures()
		pic.type = 3
		audio.add_picture(pic)
		audio.save()
	return 'changed', f'type {pic.type} -> 3'


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument('paths', nargs='+', type=Path, help='audio files or folders to scan')
	parser.add_argument('--write', action='store_true', help='save the change (default: dry run)')
	args = parser.parse_args()
	logging.basicConfig(level=logging.INFO, format='%(message)s')

	counts = {'changed': 0, 'front': 0, 'multi': 0, 'empty': 0, 'errors': 0}
	for target in args.paths:
		if not target.exists():
			log.error('%s: no such path', target)
			counts['errors'] += 1
			continue
		for path in audio_files(target):
			try:
				reason, detail = retype(path, args.write)
			except (MutagenError, OSError, ValueError) as e:
				log.error('%s: %s', path, e)
				counts['errors'] += 1
				continue
			counts[reason] += 1
			if reason == 'multi':
				log.info('%s: %s', path, detail)
	log.info(
		'%s: %d changed, %d already front, %d with multiple pictures, %d with no picture, %d error(s)',
		'wrote' if args.write else 'dry run',
		counts['changed'],
		counts['front'],
		counts['multi'],
		counts['empty'],
		counts['errors'],
	)


if __name__ == '__main__':
	main()
