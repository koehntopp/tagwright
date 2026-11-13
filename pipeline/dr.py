"""Step 1, dynamic range: the `drcalc` binary writes DYNAMIC_RANGE and ALBUM_DR (ADR 0036, 0006).

drcalc (https://github.com/koehntopp/drcalc) is a Rust port of drmeter. It analyses the tracks in parallel,
takes everything below the album folder as one album (`--album overall`, ADR 0076: ALBUM_DR is the mean over all
discs, whatever the disc folders are called), and leaves other
tags, ReplayGain values and pictures alone. It recomputes every track; the result is deterministic.
"""

import logging
from pathlib import Path

from pipeline.tools import Context, StepError, tail, tool

log = logging.getLogger(__name__)


def run(album: Path, ctx: Context) -> None:
	"""Write the DR tags of an album. A track that cannot be measured (shorter than 12 s) makes drcalc exit
	with 1 after it has tagged the others; that is an error for the step, not a reason to lose the others."""
	log.info('Starting dynamic range calculation in %s', album)
	result = ctx.run([tool('drcalc'), '--write-tags', '--quiet', '--album', 'overall', str(album)])
	if result.returncode != 0:
		raise StepError(f'drcalc exited with code {result.returncode}: {tail(result.stdout)}')
	log.info('Dynamic range done for %s', album.name)
