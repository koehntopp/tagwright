# ADR 0019: Version control and releases

- **Status**: Superseded by [ADR 0020](0020-work-directly-on-main.md)
- **Date**: 2026-11-08

## Decision

- Repository: public GitHub repository `koehntopp/tagwright`; `main` is the only long-lived branch.
- Work is done on short-lived branches and merged into `main` by fast-forward after the owner approves the merge; the branch is then deleted locally and on the remote. An agent does not push to `main` or merge without the owner's instruction.
- Releases are annotated tags `vMAJOR.MINOR` on `main`: `v0.1` (first working version), `v0.2` (track editor, track list buttons, album overrides, internal tag editor). Tags are created on request.
- Commit messages say what changed and why in one or two lines. Agent-made commits end with the attribution line required by the tool configuration in use.
- Never commit `data/`, `node_modules/`, `__pycache__/`, API keys, or music files. `static/ui/` (the built frontend) is committed ([0029](0029-nextjs-frontend-static-export.md)); `ui/node_modules/`, `ui/.next/` and `ui/out/` are not.
- The discogs repository is separate and has its own workflow; edits there are made only on request, and are described in the ADR that motivated them.

## Consequences

- History stays linear and `git checkout vX.Y` restores a known state.
