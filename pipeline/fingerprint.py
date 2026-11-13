"""Step 3, AcoustID fingerprints: the `fpscan` binary writes ACOUSTID_FINGERPRINT (ADR 0075, 0036, 0006).

fpscan (https://github.com/koehntopp/fpscan) decodes, fingerprints (the first 120 s, which is what AcoustID matches on)
and tags in one process, in parallel. It skips files that already carry a fingerprint (either spelling), keeps other
tags, ReplayGain values and pictures, and reads and writes a file's tags in one step right before saving, so tags
written meanwhile are not lost (ADR 0032).
"""

import logging
from pathlib import Path

from pipeline.tools import Context, StepError, tail, tool

log = logging.getLogger(__name__)


def run(album: Path, ctx: Context) -> None:
	"""Write the fingerprints an album lacks. A file that cannot be fingerprinted makes fpscan exit with 1 after it
	has tagged the others; that is an error for the step, not a reason to lose the others."""
	log.info('Starting AcoustID fingerprint generation in %s', album)
	result = ctx.run([tool('fpscan'), '--write-tags', '--quiet', str(album)])
	if result.returncode != 0:
		raise StepError(f'fpscan exited with code {result.returncode}: {tail(result.stdout)}')
	log.info('AcoustID fingerprints done for %s', album.name)
