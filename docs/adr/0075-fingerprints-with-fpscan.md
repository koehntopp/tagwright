# ADR 0075: Fingerprints with fpscan instead of fpcalc

- **Status**: Accepted
- **Date**: 2026-11-13
- **Supersedes**: [0073](0073-fingerprints-despite-a-decoding-error.md) (nothing to tolerate any more), and in part [0036](0036-standalone-pipeline-package.md) and [0003](0003-deployment-web-app-in-docker.md) (`fpcalc` is no longer an external tool or part of the image)

## Context

The fingerprint step ran `fpcalc` (Chromaprint, which decodes through FFmpeg) once per file from a thread pool and wrote the tag with mutagen. FFmpeg's decoder differences cost three fixes ([0025](0025-fingerprint-length-in-discogs-repository.md), [0073](0073-fingerprints-despite-a-decoding-error.md)). The owner wrote [`fpscan`](https://github.com/koehntopp/fpscan), a Rust tool in the style of `drcalc` and `rsgain`: it decodes (Symphonia), fingerprints (the Chromaprint algorithm 2 in Rust) and tags (lofty) in one process, over a whole directory, in parallel, FLAC and MP3 included.

## Decision

- The fingerprint step runs `fpscan --write-tags --quiet <album>` once per album and writes `ACOUSTID_FINGERPRINT`. `fpscan` is found on `PATH` like `drcalc` and `rsgain` (`FPSCAN_BIN` overrides it).
- `fpscan` skips a file that already has a fingerprint (either spelling), fingerprints the first 120 seconds, keeps all other tags and pictures, and exits with 1 after tagging the others when a file fails. That exit code is the step's error, with the tool's last lines in the message, as for `drcalc`.
- Tagwright no longer parses `fpcalc` output, no longer writes the fingerprint tag itself and no longer treats a non-zero exit with a printed fingerprint as success ([0073](0073-fingerprints-despite-a-decoding-error.md)): `fpscan` does not depend on FFmpeg's end-of-stream errors.
- Tag name, status rule and the Fingerprints step's place in the run are unchanged ([0006](0006-status-model-and-pipeline-steps.md), [0054](0054-album-status-and-steps-consolidated.md), [0036](0036-standalone-pipeline-package.md)).
- The Docker image builds `fpscan` in its own Rust stage from a pinned commit (it has no release yet; a release with checked binaries like `drcalc`'s replaces this) and no longer installs `libchromaprint-tools`.

## Consequences

- Fingerprints written by `fpscan` are not byte-identical to `fpcalc`'s (0.3 to 1.4 % of the bits differ on a sample); AcoustID matching tolerates this. Existing fingerprints are left alone.
- The image build needs a Rust toolchain stage (a few minutes per architecture); the final image gets smaller.
- The step runs all files in one process: Stop ends it with the other tools ([0008](0008-job-model.md)); progress is per album, not per file.
- Verified on scratch files: a FLAC with a stray ID3v1 block and an MP3 are fingerprinted (exit 0); the step test suite uses a fake `fpscan`, plus one test with the real binary when it is on `PATH`. Not verified: the Docker build and the amd64 image.
