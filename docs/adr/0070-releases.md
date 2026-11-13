# ADR 0070: Releases: version tag, versioned image, GitHub release

- **Status**: Accepted
- **Date**: 2026-11-13

## Context

Versions 0.1 and 0.2 were tagged early without release notes or images. Release notes are kept in `CHANGELOG.md` ([0069](0069-release-notes-and-commit-descriptions.md)) and the image is published by a workflow ([0063](0063-publish-the-image-on-ghcr.md)).

## Decision

- A release is made only when the owner asks. Versions are `vMAJOR.MINOR.PATCH` tags on `main`.
- Steps: (1) in `CHANGELOG.md` rename `## Unreleased` to `## X.Y.Z (date)` and add a new empty `## Unreleased` above it; commit and push. (2) Create the tag `vX.Y.Z` on that commit and push it. (3) The push starts the image workflow, which publishes `ghcr.io/koehntopp/tagwright:X.Y.Z` and `:X.Y` and moves `:latest`. (4) Create the GitHub release for the tag with the changelog section of that version as its notes (`gh release create vX.Y.Z --notes-file ...`) and mark it as the latest.
- Releases 0.1 and 0.2 exist as GitHub releases with notes from the changelog; they have no versioned image, because they were tagged before the image was published. Only `latest` and the images of later versions exist.
- The weekly workflow run and a manual run rebuild `latest` only.

## Consequences

- A version's image, tag, release page and notes carry the same number.
- Rolling back to a release is a pull of its version tag.
