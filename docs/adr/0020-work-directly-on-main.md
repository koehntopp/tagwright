# ADR 0020: Work directly on main; no feature branches

- **Status**: Accepted
- **Date**: 2026-11-08
- **Supersedes**: [ADR 0019](0019-version-control-and-releases.md)

## Context

ADR 0019 had agents work on short-lived branches and merge after approval. The owner works alone, reviews by running the app, and had to ask for every branch to be merged and deleted. The branches added steps and no safety the owner wanted.

## Decision

- **`main` is the only branch**, locally and on GitHub `koehntopp/tagwright` (private). Agents do **not** create branches, worktrees for branches, or pull requests, and do not leave any behind. A branch found other than `main` is merged or deleted on the owner's say-so, and the owner's standing wish is none.
- Work is committed **directly on `main`** in small commits after the change has been verified ([0018](0018-verification.md)), and pushed to `origin main` right after. History stays linear.
- `git checkout vX.Y` and `git revert` are the ways back, not branches.
- Releases stay annotated tags `vMAJOR.MINOR` on `main` (`v0.1`, `v0.2`), created when the owner asks.
- Commit messages say what changed and why in one or two lines. Agent-made commits end with the attribution line required by the tool configuration in use.
- Never commit `data/`, `node_modules/`, `__pycache__/`, API keys, or music files. `static/app.css` is committed ([0005](0005-technology-stack-and-conventions.md)).
- Never force-push, rewrite published history, or delete tags without the owner's instruction.
- The discogs repository is separate and has its own workflow; edits there are made only on request, and are described in the ADR that motivated them.

## Consequences

- A bad change reaches `main` immediately; verification before the commit is therefore mandatory.
- The `renovate/configure` branch on GitHub is not ours and is left alone.
