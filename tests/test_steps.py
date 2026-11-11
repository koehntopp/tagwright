"""The DR, ReplayGain and fingerprint steps and the runner, with fake tools and (when installed) the real ones (ADR 0036)."""

import logging
import shutil
import stat
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from mutagen.flac import FLAC

from pipeline import dr, fingerprint, replaygain, run
from pipeline.config import Config
from pipeline.http import ApiError
from pipeline.tools import Context, StepError, Stopped, tail, tool

from .conftest import MakeFlac

Install = Callable[[str, str], Path]


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
	return Context(Config(data_dir=tmp_path / 'data'))


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Install:
	"""install(name, python_body) makes <name>_BIN point at a small Python script; argv and a log dir are in scope."""
	bin_dir = tmp_path / 'bin'
	bin_dir.mkdir()

	def make(name: str, body: str) -> Path:
		script = bin_dir / name
		script.write_text(f'#!{sys.executable}\nimport sys\nargs = sys.argv[1:]\n{body}\n')
		script.chmod(script.stat().st_mode | stat.S_IXUSR)
		monkeypatch.setenv(f'{name.upper()}_BIN', str(script))
		return script

	return make


def album(make_flac: MakeFlac, root: Path, count: int = 2) -> Path:
	for i in range(1, count + 1):
		make_flac(root / f'{i:02d}.flac', TITLE=f'T{i}')
	return root


class TestTools:
	def test_tool_prefers_the_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
		monkeypatch.setenv('SOMETOOL_BIN', '/x/sometool')
		assert tool('sometool') == '/x/sometool'

	def test_a_missing_tool_is_a_step_error_that_says_what_to_do(
		self, monkeypatch: pytest.MonkeyPatch
	) -> None:
		monkeypatch.delenv('NOSUCHTOOL_BIN', raising=False)
		with pytest.raises(StepError, match='NOSUCHTOOL_BIN'):
			tool('nosuchtool')

	def test_run_captures_stdout_and_stderr_together(self, ctx: Context) -> None:
		r = ctx.run(
			[
				sys.executable,
				'-c',
				'import sys; print("a"); print("b", file=sys.stderr); sys.exit(3)',
			]
		)
		assert r.returncode == 3
		assert 'a' in r.stdout
		assert 'b' in r.stdout

	def test_an_unstartable_tool_is_a_step_error(self, ctx: Context) -> None:
		with pytest.raises(StepError, match='could not start'):
			ctx.run(['/no/such/binary'])

	def test_tail_keeps_the_last_lines(self) -> None:
		assert tail('1\n2\n3\n4\n5\n6\n7\n', lines=3) == '5 | 6 | 7'

	def test_stop_ends_a_running_tool(self, ctx: Context) -> None:
		errors: list[BaseException] = []

		def worker() -> None:
			try:
				ctx.run([sys.executable, '-c', 'import time; time.sleep(60)'])
			except BaseException as e:  # collected so the test thread can assert on it
				errors.append(e)

		t = threading.Thread(target=worker)
		t.start()
		deadline = time.time() + 5
		while not ctx._procs and time.time() < deadline:
			time.sleep(0.02)
		ctx.kill()
		t.join(10)
		assert not t.is_alive()
		assert [type(e) for e in errors] == [Stopped]

	def test_nothing_runs_after_stop(self, ctx: Context) -> None:
		ctx.stop.set()
		with pytest.raises(Stopped):
			ctx.run([sys.executable, '-c', 'pass'])


class TestDr:
	def test_runs_drcalc_with_write_tags_on_the_album(
		self, ctx: Context, install: Install, tmp_path: Path
	) -> None:
		install('drcalc', f'open({str(tmp_path / "args")!r}, "w").write(" ".join(args))')
		dr.run(tmp_path / 'album', ctx)
		assert (
			tmp_path / 'args'
		).read_text() == f'--write-tags --quiet --album folder {tmp_path / "album"}'

	def test_a_failing_drcalc_is_a_step_error_with_its_output(
		self, ctx: Context, install: Install, tmp_path: Path
	) -> None:
		install('drcalc', 'print("track too short"); sys.exit(1)')
		with pytest.raises(StepError, match='code 1: track too short'):
			dr.run(tmp_path, ctx)


class TestReplayGain:
	def test_preset_has_the_configured_values(self) -> None:
		text = replaygain.preset(
			Config(
				Path('.'),
				rsgain_loudness=-18,
				rsgain_clip_mode='p',
				rsgain_max_peak=-2.5,
				rsgain_true_peak=False,
			)
		)
		assert 'TargetLoudness=-18\n' in text
		assert 'ClipMode=p\n' in text
		assert 'MaxPeakLevel=-2.5\n' in text
		assert 'TruePeak=false\n' in text
		assert 'Album=true\nTagMode=i\n' in text

	def test_the_defaults_are_the_discogs_ones(self) -> None:
		text = replaygain.preset(Config(Path('.')))
		assert 'TargetLoudness=-14\nClipMode=a\nMaxPeakLevel=-1.0\nTruePeak=true\n' in text

	def test_skip_only_when_every_file_has_album_gain(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		make_flac(tmp_path / 'a' / '1.flac', REPLAYGAIN_ALBUM_GAIN='-5 dB')
		make_flac(
			tmp_path / 'a' / '2.flac', REPLAYGAIN_TRACK_GAIN='-5 dB'
		)  # track gain alone is not enough
		assert replaygain.has_album_gain(tmp_path / 'a') is False
		f = FLAC(tmp_path / 'a' / '2.flac')
		f['REPLAYGAIN_ALBUM_GAIN'] = ['-5 dB']
		f.save()
		assert replaygain.has_album_gain(tmp_path / 'a') is True
		assert replaygain.has_album_gain(tmp_path / 'empty') is False

	def test_command_uses_s_only_with_skip_enabled_and_album_gain(
		self, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		make_flac(tmp_path / 'a' / '1.flac', REPLAYGAIN_ALBUM_GAIN='-5 dB')
		on = replaygain.command(tmp_path / 'a', Config(Path('.')), 'p.ini')
		assert on == ['rsgain', 'easy', '-q', '-S', '-p', 'p.ini', str(tmp_path / 'a')]
		off = replaygain.command(tmp_path / 'a', Config(Path('.'), rsgain_skip=False), 'p.ini')
		assert '-S' not in off
		make_flac(tmp_path / 'b' / '1.flac')
		assert '-S' not in replaygain.command(tmp_path / 'b', Config(Path('.')), 'p.ini')

	def test_runs_rsgain_with_a_preset_that_is_removed_afterwards(
		self, ctx: Context, install: Install, tmp_path: Path
	) -> None:
		install(
			'rsgain',
			f'import shutil; shutil.copy(args[args.index("-p") + 1], {str(tmp_path / "seen.ini")!r}); open({str(tmp_path / "preset_path")!r}, "w").write(args[args.index("-p") + 1])',
		)
		replaygain.run(tmp_path / 'a', ctx)
		assert 'TargetLoudness=-14' in (tmp_path / 'seen.ini').read_text()
		assert not Path((tmp_path / 'preset_path').read_text()).exists()

	def test_a_failing_rsgain_is_a_step_error_and_still_removes_the_preset(
		self, ctx: Context, install: Install, tmp_path: Path
	) -> None:
		install(
			'rsgain',
			f'open({str(tmp_path / "preset_path")!r}, "w").write(args[args.index("-p") + 1]); print("boom"); sys.exit(2)',
		)
		with pytest.raises(StepError, match='code 2: boom'):
			replaygain.run(tmp_path, ctx)
		assert not Path((tmp_path / 'preset_path').read_text()).exists()


FPCALC = (
	'name = args[-1]\n'
	'if name.endswith("bad.flac"):\n'
	'\tprint("ERROR: decoding failed"); sys.exit(3)\n'
	'if name.endswith("empty.flac"):\n'
	'\tprint("DURATION=1"); sys.exit(0)\n'
	'print("DURATION=0.2"); print("FINGERPRINT=FP-" + name.rsplit("/", 1)[-1])\n'
)


class TestFingerprint:
	def test_parse(self) -> None:
		assert fingerprint.parse('DURATION=12\nFINGERPRINT=AQAA \n') == 'AQAA'
		assert fingerprint.parse('DURATION=12\n') == ''
		assert fingerprint.parse('') == ''

	def test_existing_reads_both_spellings(self) -> None:
		assert fingerprint.existing({'ACOUSTID_FINGERPRINT': [' x ']}) == 'x'
		assert fingerprint.existing({'ACOUSTID FINGERPRINT': ['y']}) == 'y'
		assert fingerprint.existing({'ACOUSTID_FINGERPRINT': [' ']}) == ''
		assert fingerprint.existing(None) == ''

	def test_writes_a_fingerprint_for_every_file_that_lacks_one(
		self, ctx: Context, install: Install, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		install(
			'fpcalc',
			FPCALC + f'open({str(tmp_path / "calls")!r}, "a").write(" ".join(args) + "\\n")',
		)
		a = album(make_flac, tmp_path / 'a')
		f = FLAC(a / '02.flac')
		f['ACOUSTID_FINGERPRINT'] = ['KEEP']
		f.save()
		fingerprint.run(a, ctx)
		assert FLAC(a / '01.flac')['ACOUSTID_FINGERPRINT'] == ['FP-01.flac']
		assert FLAC(a / '02.flac')['ACOUSTID_FINGERPRINT'] == ['KEEP']  # never recomputed
		calls = (tmp_path / 'calls').read_text().splitlines()
		assert len(calls) == 1
		assert calls[0].startswith('-length 120 ')  # the first 120 s only
		assert FLAC(a / '01.flac')['TITLE'] == ['T1']  # other tags survive

	def test_the_legacy_spelling_counts_as_present(
		self, ctx: Context, install: Install, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		install('fpcalc', 'sys.exit(9)')  # must not be called
		a = album(make_flac, tmp_path / 'a', 1)
		f = FLAC(a / '01.flac')
		f['ACOUSTID FINGERPRINT'] = ['OLD']
		f.save()
		fingerprint.run(a, ctx)

	def test_no_files_to_do_needs_no_tool(
		self, ctx: Context, make_flac: MakeFlac, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
	) -> None:
		monkeypatch.delenv('FPCALC_BIN', raising=False)
		monkeypatch.setenv('PATH', '')
		a = album(make_flac, tmp_path / 'a', 1)
		f = FLAC(a / '01.flac')
		f['ACOUSTID_FINGERPRINT'] = ['x']
		f.save()
		fingerprint.run(a, ctx)

	def test_failures_are_per_file_and_the_others_are_still_written(
		self,
		ctx: Context,
		install: Install,
		make_flac: MakeFlac,
		tmp_path: Path,
		caplog: pytest.LogCaptureFixture,
	) -> None:
		install('fpcalc', FPCALC)
		a = tmp_path / 'a'
		for name in ('01.flac', 'bad.flac', 'empty.flac', 'zz.flac'):
			make_flac(a / name)
		with caplog.at_level(logging.INFO), pytest.raises(StepError, match='2 fingerprint'):
			fingerprint.run(a, ctx)
		assert FLAC(a / '01.flac')['ACOUSTID_FINGERPRINT'] == ['FP-01.flac']
		assert FLAC(a / 'zz.flac')['ACOUSTID_FINGERPRINT'] == ['FP-zz.flac']
		assert 'ACOUSTID_FINGERPRINT' not in FLAC(a / 'bad.flac')
		assert 'ACOUSTID_FINGERPRINT' not in FLAC(a / 'empty.flac')
		assert 'generated for 2 of 4 files' in caplog.text
		assert 'decoding failed' in caplog.text
		assert 'printed no fingerprint' in caplog.text

	def test_tags_written_meanwhile_are_not_lost(
		self, ctx: Context, install: Install, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		a = album(make_flac, tmp_path / 'a', 1)
		# the tool itself writes a tag into the file while it "calculates" (what drcalc or rsgain could do)
		install(
			'fpcalc',
			f'from mutagen.flac import FLAC\nf = FLAC({str(a / "01.flac")!r}); f["LATE"] = ["kept"]; f.save()\n'
			+ FPCALC,
		)
		fingerprint.run(a, ctx)
		t = FLAC(a / '01.flac')
		assert t['LATE'] == ['kept']
		assert t['ACOUSTID_FINGERPRINT'] == ['FP-01.flac']

	def test_a_stop_ends_the_step(
		self, ctx: Context, install: Install, make_flac: MakeFlac, tmp_path: Path
	) -> None:
		install('fpcalc', FPCALC)
		a = album(make_flac, tmp_path / 'a')
		ctx.stop.set()
		with pytest.raises(Stopped):
			fingerprint.run(a, ctx)


class TestRun:
	def steps(
		self, log: list[str], fail: dict[str, BaseException] | None = None
	) -> list[tuple[str, run.StepFn]]:
		def make(name: str) -> run.StepFn:
			def step(album: Path, ctx: Context) -> None:
				log.append(name)
				if fail and name in fail:
					raise fail[name]

			return step

		return [(n, make(n)) for n in ('one', 'two', 'three')]

	def test_all_steps_run_in_order(self, ctx: Context, tmp_path: Path) -> None:
		seen: list[str] = []
		assert run.run_album(tmp_path, ctx, self.steps(seen)) is True
		assert seen == ['one', 'two', 'three']

	def test_a_failing_step_is_logged_and_the_rest_still_run(
		self, ctx: Context, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		seen: list[str] = []
		fail = {'one': StepError('boom'), 'two': ApiError(404, 'Discogs: not found')}
		with caplog.at_level(logging.ERROR):
			assert run.run_album(tmp_path, ctx, self.steps(seen, fail)) is False
		assert seen == ['one', 'two', 'three']
		assert 'one failed: boom' in caplog.text
		assert 'two failed: Discogs: not found' in caplog.text

	def test_a_crash_in_a_step_does_not_end_the_run(
		self, ctx: Context, tmp_path: Path, caplog: pytest.LogCaptureFixture
	) -> None:
		seen: list[str] = []
		with caplog.at_level(logging.ERROR):
			assert run.run_album(tmp_path, ctx, self.steps(seen, {'one': KeyError('x')})) is False
		assert seen == ['one', 'two', 'three']
		assert 'one crashed' in caplog.text

	def test_stop_ends_the_run_at_once(self, ctx: Context, tmp_path: Path) -> None:
		seen: list[str] = []
		steps = self.steps(seen, {'two': Stopped()})
		with pytest.raises(Stopped):
			run.run_album(tmp_path, ctx, steps)
		assert seen == ['one', 'two']

	def test_a_stop_before_the_first_step_runs_nothing(self, ctx: Context, tmp_path: Path) -> None:
		seen: list[str] = []
		ctx.stop.set()
		with pytest.raises(Stopped):
			run.run_album(tmp_path, ctx, self.steps(seen))
		assert seen == []

	def test_on_step_is_told_before_each_step(self, ctx: Context, tmp_path: Path) -> None:
		told: list[str] = []
		seen: list[str] = []
		run.run_album(tmp_path, ctx, self.steps(seen), on_step=told.append)
		assert told == ['one', 'two', 'three']

	def test_the_default_order(self) -> None:
		assert [name for name, _ in run.STEPS] == [
			'dot_clean',
			'Dynamic range',
			'ReplayGain',
			'Fingerprints',
			'Discogs tags',
			'Lyrics',
		]


def noise_album(root: Path, tracks: int = 2, seconds: int = 15, rate: int = 44100) -> Path:
	"""Real audio for the real tools: drcalc needs at least 12 s, fpcalc and rsgain a signal."""
	rng = np.random.default_rng(1)
	for i in range(1, tracks + 1):
		root.mkdir(parents=True, exist_ok=True)
		samples = (
			(rng.normal(0, 0.1 * i, (seconds * rate, 2)) * 32767)
			.clip(-32768, 32767)
			.astype('int16')
		)
		sf.write(root / f'{i:02d}.flac', samples, rate, format='FLAC')
	return root


needs = pytest.mark.skipif


@needs(not shutil.which('drcalc'), reason='drcalc is not installed')
def test_the_real_drcalc_writes_the_dr_tags(ctx: Context, tmp_path: Path) -> None:
	a = noise_album(tmp_path / 'a')
	dr.run(a, ctx)
	for f in sorted(a.glob('*.flac')):
		t = FLAC(f)
		assert t['DYNAMIC_RANGE'][0].isdigit()
		assert t['ALBUM_DR'][0].isdigit()
		assert 'DYNAMIC RANGE' not in t  # the spaced foobar2000 key is not written (ADR 0027)
	assert FLAC(a / '01.flac')['ALBUM_DR'] == FLAC(a / '02.flac')['ALBUM_DR']


@needs(not shutil.which('drcalc'), reason='drcalc is not installed')
def test_the_real_drcalc_treats_disc_folders_as_one_album(ctx: Context, tmp_path: Path) -> None:
	noise_album(tmp_path / 'a' / 'Disc 1', 1)
	noise_album(tmp_path / 'a' / 'Disc 2', 1)
	dr.run(tmp_path / 'a', ctx)
	assert (
		FLAC(tmp_path / 'a' / 'Disc 1' / '01.flac')['ALBUM_DR']
		== FLAC(tmp_path / 'a' / 'Disc 2' / '01.flac')['ALBUM_DR']
	)


@needs(not shutil.which('drcalc'), reason='drcalc is not installed')
def test_the_real_drcalc_keeps_other_tags_and_fails_on_short_tracks(
	ctx: Context, make_flac: MakeFlac, tmp_path: Path
) -> None:
	a = noise_album(tmp_path / 'a', 1)
	f = FLAC(a / '01.flac')
	f['ARTIST'] = ['Keep']
	f['REPLAYGAIN_ALBUM_GAIN'] = ['-3 dB']
	f.save()
	make_flac(a / '02.flac')  # 0.2 s: cannot be measured
	with pytest.raises(StepError):
		dr.run(a, ctx)
	t = FLAC(a / '01.flac')
	assert t['ARTIST'] == ['Keep']
	assert t['REPLAYGAIN_ALBUM_GAIN'] == ['-3 dB']
	assert t['DYNAMIC_RANGE'][0].isdigit()  # the measurable track was still tagged


@needs(not shutil.which('fpcalc'), reason='fpcalc is not installed')
def test_the_real_fpcalc_writes_a_fingerprint(ctx: Context, tmp_path: Path) -> None:
	a = noise_album(tmp_path / 'a', 1, seconds=5)
	fingerprint.run(a, ctx)
	assert len(FLAC(a / '01.flac')['ACOUSTID_FINGERPRINT'][0]) > 20


@needs(not shutil.which('rsgain'), reason='rsgain is not installed')
def test_the_real_rsgain_writes_replaygain_tags(ctx: Context, tmp_path: Path) -> None:
	a = noise_album(tmp_path / 'a', 2, seconds=5)
	replaygain.run(a, ctx)
	t = FLAC(a / '01.flac')
	assert t['REPLAYGAIN_TRACK_GAIN']
	assert t['REPLAYGAIN_ALBUM_GAIN']
	assert replaygain.has_album_gain(a)
