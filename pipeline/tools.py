"""Running the external tools (drcalc, rsgain, fpcalc) so that Stop can end them (ADR 0008, 0036)."""

import logging
import os
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.config import Config

log = logging.getLogger(__name__)

KILL_AFTER = 10.0  # seconds between SIGTERM and SIGKILL on Stop


class StepError(Exception):
	"""A step could not finish; the message goes to the job log."""


class Stopped(Exception):
	"""The user pressed Stop; the run ends without running the remaining steps."""


def tool(name: str) -> str:
	"""Path of an external tool: $<NAME>_BIN if set, else the first match on PATH."""
	override = os.environ.get(f'{name.upper()}_BIN')
	found = override or shutil.which(name)
	if not found:
		raise StepError(f'{name} is not installed (not on PATH, and {name.upper()}_BIN is not set)')
	return found


@dataclass
class Context:
	"""Shared by the steps of one run: settings, the Stop flag and the child processes running now."""

	cfg: Config
	stop: threading.Event = field(default_factory=threading.Event)
	_procs: set[subprocess.Popen[str]] = field(default_factory=set)
	_lock: threading.Lock = field(default_factory=threading.Lock)

	def check(self) -> None:
		"""Raise Stopped when Stop was pressed; steps call this between files."""
		if self.stop.is_set():
			raise Stopped

	def run(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
		"""Run a tool to the end; stdout and stderr come back together. Raises Stopped after Stop."""
		self.check()
		try:
			p = subprocess.Popen(
				args,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
				cwd=cwd,
				start_new_session=True,  # own process group, so Stop ends the tool and what it started
			)
		except OSError as e:
			raise StepError(f'could not start {args[0]}: {e}') from e
		with self._lock:
			self._procs.add(p)
		try:
			out, _ = p.communicate()
		finally:
			with self._lock:
				self._procs.discard(p)
		self.check()
		return subprocess.CompletedProcess(args, p.returncode, out)

	def kill(self) -> None:
		"""Stop: set the flag and end every running tool (SIGTERM, SIGKILL after KILL_AFTER s)."""
		self.stop.set()
		with self._lock:
			procs = list(self._procs)
		for p in procs:
			_signal(p, signal.SIGTERM)
			threading.Timer(KILL_AFTER, _kill_if_alive, args=(p,)).start()


def _signal(p: subprocess.Popen[str], sig: int) -> None:
	try:
		os.killpg(p.pid, sig)  # start_new_session made the group id the pid
	except ProcessLookupError:
		pass


def _kill_if_alive(p: subprocess.Popen[str]) -> None:
	if p.poll() is None:
		_signal(p, signal.SIGKILL)


def tail(output: str, lines: int = 5) -> str:
	"""The last lines of a tool's output, for an error message."""
	return ' | '.join(output.strip().splitlines()[-lines:])
