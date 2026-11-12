# ADR 0061: Renovate for dependency updates

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

Dependabot covers the npm packages, the Python tools in `uv.lock` and security alerts, but not the runtime dependencies in the PEP 723 header of `app.py`, nor the versions of `rsgain` and `drcalc` that the `Dockerfile` downloads from GitHub releases ([0003](0003-deployment-web-app-in-docker.md)).

## Decision

- Renovate runs on the repository (GitHub app), configured in `renovate.json`: `config:recommended`, weekly (Europe/Berlin), non-major updates grouped in one pull request, major updates one by one. It reads the `app.py` header (`pep723` manager) and the two `ARG ..._VERSION` lines of the `Dockerfile` (each has a `# renovate:` comment naming the GitHub repository).
- Dependabot security alerts and security updates stay on; Renovate does not replace them.
- Updates arrive as pull requests from branches `renovate/*`. They are the bot's: agents do not create, push to or delete them ([0020](0020-work-directly-on-main.md), AGENTS.md). Nothing is merged without the owner.

## Consequences

- One more bot on the repository. A merged update that touches `app.py`, the `Dockerfile` or the UI needs a rebuilt image or `static/ui/`, which stays a manual step.
