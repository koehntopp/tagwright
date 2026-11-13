# ADR 0069: Release notes and detailed commit descriptions

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

Changes reach the server continuously, from commits on `main` ([0020](0020-work-directly-on-main.md)) through the published image ([0063](0063-publish-the-image-on-ghcr.md)). Without a record kept as the work happens, writing release notes later means reconstructing them from commit subjects.

## Decision

- **`CHANGELOG.md`** holds the release notes. Every functional change or bug fix adds an entry under `## Unreleased` in the same commit: one entry per change, grouped as Added, Changed, Fixed, Removed or Security, written for a user (what is different for them) and naming the ADR when there is one. Refactors, tests, documentation, CI and dependency bumps without a user-visible effect need no entry; the commit body then says "No release note". When a release is tagged by the owner, `Unreleased` becomes the version's heading with its date.
- **Every commit has a detailed description**: a subject line (imperative, up to about 72 characters) and a body with *why*, *what*, *how it was checked* (including what was not verified) and *which ADRs apply*. A one-line message is not accepted.
- The rule is in AGENTS.md (section 6 and the final checklist), so every agent follows it.

## Consequences

- A release's notes are the sum of its commits' entries: nothing to reconstruct.
- The history before this ADR has no entries; they are not backfilled unless the owner asks.
