"""Pipeline settings that are not secrets (ADR 0036). The defaults are what the discogs `config.py` had."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
	data_dir: Path  # the MusicBrainz cache lives in <data_dir>/musicbrainz
	cover_max_size: int = 1500  # embedded covers larger than this (either side, px) are resized
	musicbrainz_languages: bool = True  # write LYRICS_LANGUAGE from MusicBrainz
	rsgain_loudness: int = -14  # target loudness in LUFS
	rsgain_clip_mode: str = 'a'  # clipping protection: n = none, p = positive only, a = always
	rsgain_max_peak: float = -1.0  # dBTP, for the clipping protection
	rsgain_true_peak: bool = True
	rsgain_skip: bool = True  # skip an album that already has album gain (ADR 0028)
