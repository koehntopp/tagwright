"""Disc and track numbers from Discogs track positions (ADR 0053, 0101).

Discogs writes positions in several styles: `1-3` or `2.3` (disc 1 or 2, track 3), a media label in front of them
(`CD2-3`, `SACD1-4`, `BD1-2`), a media label without a disc number (`SACD-1`, `CD-1`, `DVD-1`: one disc per
label), plain numbers that restart under a `Disc N` heading, and vinyl sides (`A1`). Positions are read in
tracklist order; `place` returns None for a position that names no disc (vinyl, plain numbers without a heading,
empty), which the caller numbers in sequence on disc 1.
"""

import re

# A heading that names a disc: 'Disc 2', 'CD 2', 'SACD 1', 'BD 1', 'Blu-ray 1', 'Disk 3' (any case, space optional)
DISC_HEADING = r'(?:SA-?CD|HDCD|CD|DVD|BD|Blu-?ray|Disc|Disk)\s*(\d+)\b'
# A media label: two or more letters, so a vinyl side (A1, B2) is never one
_DISC_TRACK = re.compile(r'(?:[A-Za-z]{2,})?(\d+)[-.](\d+)')
_LABEL_TRACK = re.compile(r'([A-Za-z]{2,})[-.]?(\d+)')


class Positions:
	"""Reads one release's positions in tracklist order; `heading` for every heading, `place` for every track."""

	def __init__(self) -> None:
		self.head = 0  # the disc of the last heading that named one
		self.labels: dict[str, int] = {}  # media label -> its disc, for labels without a heading
		self.top = 0  # the highest disc so far

	def heading(self, title: str) -> None:
		if m := re.match(DISC_HEADING, title.strip(), re.I):
			self.head = int(m[1])

	def place(self, position: str) -> tuple[int, int] | None:
		pos = position.strip()
		if m := _DISC_TRACK.fullmatch(pos):
			out = int(m[1]), int(m[2])
		elif m := _LABEL_TRACK.fullmatch(pos):
			# a 'Disc N' heading decides; else every new label is the next disc (SACD-1.. disc 1, CD-1.. disc 2)
			disc = self.head or self.labels.setdefault(m[1].upper(), self.top + 1)
			out = disc, int(m[2])
		elif self.head and pos.isdigit():
			out = self.head, int(pos)
		else:
			return None
		self.top = max(self.top, out[0])
		return out
