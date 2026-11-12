"""Step 2, ReplayGain: `rsgain easy` writes the REPLAYGAIN_* tags (ADR 0006, 0028, 0036)."""

import logging
import os
import tempfile
from pathlib import Path

from mutagen import MutagenError

from pipeline.audio import open_audio
from pipeline.config import Config
from pipeline.layout import flacs
from pipeline.tools import Context, StepError, tail, tool

log = logging.getLogger(__name__)


def preset(cfg: Config) -> str:
	"""The rsgain preset (ini) for the configured loudness target and clipping protection."""
	return (
		'[Global]\n'
		f'TargetLoudness={cfg.rsgain_loudness}\n'
		f'ClipMode={cfg.rsgain_clip_mode}\n'
		f'MaxPeakLevel={cfg.rsgain_max_peak}\n'
		f'TruePeak={"true" if cfg.rsgain_true_peak else "false"}\n'
		'Album=true\n'
		'TagMode=i\n'
	)


def has_album_gain(album: Path) -> bool:
	"""True when every FLAC carries REPLAYGAIN_ALBUM_GAIN (track gain alone is not enough, ADR 0028)."""
	files = flacs(album)
	try:
		return bool(files) and all(
			(open_audio(f).tags or {}).get('REPLAYGAIN_ALBUM_GAIN') for f in files
		)
	except MutagenError, OSError:
		return False


def command(album: Path, cfg: Config, preset_file: str, binary: str = 'rsgain') -> list[str]:
	"""-S makes rsgain skip files that have any ReplayGain tag, so it is used only when the album gain is there."""
	skip = ['-S'] if cfg.rsgain_skip and has_album_gain(album) else []
	return [binary, 'easy', '-q', *skip, '-p', preset_file, str(album)]


def run(album: Path, ctx: Context) -> None:
	binary = tool('rsgain')
	handle, preset_file = tempfile.mkstemp(suffix='.ini', prefix='rsgain_')
	try:
		with os.fdopen(handle, 'w') as f:
			f.write(preset(ctx.cfg))
		cmd = command(album, ctx.cfg, preset_file, binary)
		log.info('rsgain command: %s', ' '.join(cmd))
		result = ctx.run(cmd)
	finally:
		os.unlink(preset_file)
	if result.returncode != 0:
		raise StepError(f'rsgain exited with code {result.returncode}: {tail(result.stdout)}')
	log.info('ReplayGain done for %s', album.name)
