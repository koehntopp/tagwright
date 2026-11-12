"""Running the pipeline for one album: the steps in order, failures logged, the rest still run (ADR 0036, 0004).

Order (as in nzbfix since ADR 0033): dot_clean, dynamic range, ReplayGain, fingerprints, Discogs tags, lyrics.
The steps run one after another because the first three all write tags into the same files.
"""

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from pipeline import dr, fingerprint, fixtags, lyrics, replaygain
from pipeline.http import ApiError
from pipeline.tools import Context, StepError, Stopped

log = logging.getLogger(__name__)

type StepFn = Callable[[Path, Context], None]


def dot_clean(album: Path, ctx: Context) -> None:
	"""Merge macOS AppleDouble (`._name`) files back into their files; only where the tool exists."""
	if binary := shutil.which('dot_clean'):
		ctx.run([binary, str(album)])


def discogs_tags(album: Path, ctx: Context) -> None:
	result = fixtags.fix_album(album, ctx.cfg)
	if result.skipped:
		log.warning('Discogs tags skipped for %s: %s', album.name, result.skipped)


STEPS: list[tuple[str, StepFn]] = [
	('dot_clean', dot_clean),
	('Dynamic range', dr.run),
	('ReplayGain', replaygain.run),
	('Fingerprints', fingerprint.run),
	('Discogs tags', discogs_tags),
	('Lyrics', lyrics.run),
]


def only_steps(*names: str) -> list[tuple[str, StepFn]]:
	"""The listed steps, in pipeline order (for running a single step on request, ADR 0051)."""
	return [s for s in STEPS if s[0] in names]


def run_album(
	album: Path,
	ctx: Context,
	steps: list[tuple[str, StepFn]] | None = None,
	on_step: Callable[[str], None] | None = None,
) -> bool:
	"""Run every step on the album. True when all of them finished without an error.

	A step that fails is logged and the next one still runs (they do not depend on each other's success).
	Stopped (the user pressed Stop) ends the run at once and is not caught here. `on_step(name)` is called
	before each step, so the caller can show where the run is.
	"""
	ok = True
	for name, step in STEPS if steps is None else steps:
		ctx.check()
		log.info('-- %s', name)
		if on_step:
			on_step(name)
		try:
			step(album, ctx)
		except Stopped:
			raise
		except (StepError, ApiError) as e:
			ok = False
			log.error('%s failed: %s', name, getattr(e, 'message', None) or e)
		except Exception:  # a bug in one step must not end the job thread
			ok = False
			log.exception('%s crashed', name)
	return ok
