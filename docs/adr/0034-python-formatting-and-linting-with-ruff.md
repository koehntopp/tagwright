# ADR 0034: Python formatting and linting with ruff

- **Status**: Accepted
- **Date**: 2026-11-11
- **Supersedes**: the **Style** bullet of [0005](0005-technology-stack-and-conventions.md) (tabs, single quotes; the docstring and comment guidance in that bullet stands)

## Context

The style rule of 0005 ("tabs, single quotes") was written by hand and checked by eye. The discogs repository enforces the same style with ruff (`pyproject.toml`: tab indent, single quotes, line length 100). Black was considered as the formatter and rejected: it cannot indent with tabs, and running it next to ruff would give two formatters that disagree. Which tool formats and lints is a decision that outranks agent instructions, so it is recorded here; the commands agents run stay in [AGENTS.md](../../AGENTS.md).

## Decision

- **Ruff is the only linter and formatter.** Black, isort and flake8 are not used. It runs through `uv run ruff ...`.
- **Configuration** lives in `pyproject.toml` at the repository root and is changed only by a task about tooling:
  - tab indent, single quotes, line length **100** (the same as the discogs repository);
  - lint rule sets `E4`, `E7`, `E9`, `F`, `I` (import order), `B`, `UP`;
  - `ui/`, `static/` and `data/` are excluded.
- **Code policy** that ruff and review enforce: type annotations on every function signature, class attribute and non-obvious module-level variable; `Any` only with a comment saying why; no bare `except:`; no `from x import *`; no `print()` for diagnostics (use `logging.getLogger(__name__)`); no hardcoded credentials; no mutable default arguments; no `# noqa`, `# fmt: off` or `# type: ignore` unless the narrowest form with a one-line reason.
- **Workflow**: after editing Python, agents run `ruff check --fix`, `ruff format` and `ruff check` on the changed files only; a whole-repository `ruff format` is a separate, explicitly requested commit so that reformatting never hides a behaviour change. A change is not done until `uv run ruff check .` and `uv run ruff format --check .` pass.
- **Existing code**: `app.py` predates this ADR and does not yet pass. It is brought into line in one dedicated commit that changes formatting and annotations only, never behaviour. Until that commit, the whole-repository checks may fail on `app.py`; changed files must still be clean in the parts they touch.
- Fixing a ruff finding is preferred over disabling the rule; a rule that seems wrong for this codebase is reported to the owner, then changed here.

## Consequences

- One formatter, so diffs show only real changes.
- Black-style line wrapping stays compatible (ruff format is Black-compatible except for the tab setting).
- The line length of 100 matches the discogs repository, so code moves between the two without reflowing.
- `app.py` needs a one-time conversion commit before the whole-repository checks pass.
