# ADR 0084: Deploy a locally built image on the server

- **Status**: Accepted
- **Date**: 2026-11-18
- **Supersedes**: [0063](0063-publish-the-image-on-ghcr.md) (the GHCR image as the one the server runs)

## Context

ADR 0063 moved deployment from the owner's tarball script to a GHCR image that the server pulls on every start. The workflow publishes amd64 and arm64 images, but shipping a change then needs a workflow run plus a pull, and the image that was smoke-tested on the Mac is not the one the server starts. On 2026-11-18 the owner asked for a test build and deploy. The amd64 image was built locally and checked on scratch folders (server starts, API answers, `drcalc`, `rsgain` and `fpscan` present; [0018](0018-verification.md)). The server stack still used `ghcr.io/koehntopp/tagwright:latest` with `pull_policy: always`, so `deploy-linux.sh` could not put that image into service.

## Decision

- The server's Dockge stack at `/opt/stacks/tagwright` uses `image: tagwright:latest` and has no `pull_policy`: nothing is pulled on the server.
- A change reaches the server by building `tagwright:latest` for linux/amd64 on the owner's Mac with `docker buildx build --platform linux/amd64 -t tagwright:latest --load .`, smoke-testing it on scratch folders, and running `deploy-linux.sh`: `docker save`, `scp` to the host's `/tmp`, `docker load`, then `docker compose up -d` in the stack directory. The build verifies the `drcalc` download against `SHA256SUMS` ([0036](0036-standalone-pipeline-package.md)). Only amd64 is needed on this host.
- The image is still published on ghcr.io by `.github/workflows/image.yml` — `latest` always, `X.Y.Z` and `X.Y` on a `v*` tag, native amd64 and arm64 runners, a public package with the GPL labels ([0062](0062-license-gpl-3-or-later.md)). The manual and weekly runs keep moving `latest`. A release still follows [0070](0070-releases.md) and [0071](0071-readme-and-screenshots-at-every-release.md). Those parts of 0063 remain in force.
- The two NFS mounts, the data mount, the published port and the environment of the stack are unchanged.
- The previous local image is kept under its own tag before being overwritten, so a rollback is a retag plus `docker compose up -d`. Compose changes are committed in the `/opt/stacks` git repo on the host; `git -C /opt/stacks checkout -- tagwright` restores the stack files.

## Consequences

- The server no longer follows GHCR `latest`: a workflow run alone does not change production. The owner must build, transfer, load and recreate the stack to ship a change.
- Production runs the image that was smoke-tested locally; there is no pull on a restart.
- The GHCR workflow remains useful for releases and for anyone who wants to pull a published image; it is just not the server's update path.
