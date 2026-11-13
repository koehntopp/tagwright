"""Step 3, AcoustID fingerprints: `fpcalc` over the first 120 s, written as ACOUSTID_FINGERPRINT (ADR 0006, 0036).

AcoustID matches on the first 120 seconds; decoding a whole file made fpcalc exit with 3 on some hi-res FLACs
(ADR 0025); a fingerprint that fpcalc printed despite a decoding error is used (ADR 0073). Fingerprints are computed in parallel (fpcalc is a subprocess, threads suffice) and written one file
at a time, reopening the file first so that tags written meanwhile are not lost (ADR 0032).
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mutagen import MutagenError

from pipeline.audio import open_audio
from pipeline.layout import flacs
from pipeline.tagio import touch
from pipeline.tools import Context, StepError, tail, tool

log = logging.getLogger(__name__)

TAG = 'ACOUSTID_FINGERPRINT'
LEGACY_TAG = 'ACOUSTID FINGERPRINT'  # read, never written
MAX_SECONDS = 120


def existing(tags: dict | None) -> str:
	"""The fingerprint a file already carries (either spelling), stripped; '' if none."""
	for key in (TAG, LEGACY_TAG):
		values = (tags or {}).get(key)
		if values and str(values[0]).strip():
			return str(values[0]).strip()
	return ''


def parse(output: str) -> str:
	"""The fingerprint from fpcalc's `KEY=value` lines; '' when there is none."""
	for line in output.splitlines():
		if line.startswith('FINGERPRINT='):
			return line.partition('=')[2].strip()
	return ''


def fingerprint(path: Path, ctx: Context, binary: str) -> str:
	result = ctx.run([binary, '-length', str(MAX_SECONDS), str(path)])
	fp = parse(result.stdout)
	if result.returncode != 0:
		if not fp:
			raise StepError(f'fpcalc exited with code {result.returncode}: {tail(result.stdout)}')
		# A newer ffmpeg reports bytes after the last frame (a stray ID3v1 block on a FLAC, for example) as a decoding
		# error and fpcalc exits non-zero, but it has read the whole audio and printed the fingerprint (ADR 0073).
		log.warning(
			'fpcalc exited with code %d for %s but printed a fingerprint, which is used: %s',
			result.returncode,
			path.name,
			tail(result.stdout),
		)
	if not fp:
		raise StepError('fpcalc printed no fingerprint')
	return fp


def run(album: Path, ctx: Context) -> None:
	paths = flacs(album)
	log.info('Starting AcoustID fingerprint generation in %s', album)

	def needs_fp(path: Path) -> bool:
		try:
			return not existing(open_audio(path).tags)
		except MutagenError, OSError:
			return False  # unreadable: the loop below logs it

	todo = [p for p in paths if needs_fp(p)]
	binary = tool('fpcalc') if todo else ''
	calculated, failed = 0, 0
	with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
		futures = {p: pool.submit(fingerprint, p, ctx, binary) for p in todo}
		for path in paths:
			ctx.check()
			if path not in futures:
				continue
			try:
				fp = futures[path].result()
				audio = open_audio(path)  # reopen: see the module docstring
				if audio.tags is None:
					audio.add_tags()
				audio[TAG] = [fp]
				audio.save()
				touch(path)
				calculated += 1
				log.info(
					'Calculated AcoustID fingerprint for %s',
					(audio.tags.get('TITLE') or [path.name])[0],
				)
			except (StepError, MutagenError, OSError) as e:
				failed += 1
				log.error('Fingerprint calculation failed for %s: %s', path, e)
	log.info('AcoustID fingerprints generated for %d of %d files.', calculated, len(paths))
	if failed:
		raise StepError(f'{failed} fingerprint(s) could not be calculated')
