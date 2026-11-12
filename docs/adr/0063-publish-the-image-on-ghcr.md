# ADR 0063: The image is published on GitHub's container registry

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes in part**: the build-and-copy deployment of [0003](0003-deployment-web-app-in-docker.md) (a tarball built on the owner's Mac)

## Context

The image was built on the owner's Mac and copied to the server with a local script, for amd64 only. The repository is public and licensed GPL-3.0-or-later ([0062](0062-license-gpl-3-or-later.md)), so the image can be public too: it holds the public code, no settings and no keys.

## Decision

- `.github/workflows/image.yml` builds the image for **linux/amd64 and linux/arm64** on GitHub's native runners and publishes it as `ghcr.io/koehntopp/tagwright`, one manifest for both platforms. It runs on a version tag (`v*`), **weekly** (to pick up patches of the Debian base image) and by hand.
- Tags: `latest` always, and `X.Y.Z` and `X.Y` for a version tag. Pull requests and ordinary commits do not publish.
- The package is public and linked to the repository by the `org.opencontainers.image.source` label. It carries the GPL labels and the `NOTICE` offer ([0062](0062-license-gpl-3-or-later.md)).
- The server's Dockge stack uses `image: ghcr.io/koehntopp/tagwright:latest` and pulls; nothing is built on the server. `deploy-linux.sh` stays a local convenience and is not in the repository.
- Renovate keeps the action versions current ([0061](0061-renovate-for-dependency-updates.md)).

## Consequences

- A change reaches the server by publishing a new image (run the workflow, or tag a version) and pulling it in Dockge, not by building locally.
- Without a version tag only `latest` moves, so a rollback to an earlier build needs its digest.
