# ADR 0001: Record architecture decisions

- **Status**: Accepted
- **Date**: 2026-11-08

## Context

Tagwright was built iteratively with an AI agent. Decisions made in conversation are lost unless written down, and later changes then contradict them by accident.

## Decision

1. Every technical or functional decision that shapes the code is recorded as an ADR in `docs/adr/`, named `NNNN-short-title.md` with a four-digit sequence number.
2. Sections: Status, Date, Context, Decision, Consequences. Use cases go in the ADR of the feature they belong to; the overall list is in [ADR 0002](0002-purpose-scope-and-use-cases.md).
3. Statuses: `Proposed`, `Accepted`, `Superseded by ADR NNNN`, `Deprecated`.
4. An accepted ADR is **not rewritten to change a decision**. A changed decision gets a new ADR; the old one is marked `Superseded by ADR NNNN`. Corrections of wrong facts, wording, and added references may edit in place.
5. A code change that contradicts an ADR is not made until that ADR is superseded. A code change that adds or alters behaviour an ADR describes updates that ADR in the same commit.
6. [README.md](README.md) in this directory is the index; it lists every ADR with its status.

## Consequences

- Behaviour and its reasons stay findable; reviewers (human or agent) can check a change against a short, numbered list.
- Small overhead per change; accepted because the project is edited mostly by agents with no memory of earlier sessions.
- `AGENTS.md` makes rules 5 and 6 binding for agents.
