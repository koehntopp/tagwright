# AGENTS.md: rules for AI agents working on Tagwright

Tagwright is a self-hosted web app (FastAPI + one-file frontend) around the discogs `nzbfix` pipeline for FLAC albums. The architecture decision records in `docs/adr/` are **binding**. They are the specification. Code, comments and your own judgement do not outrank them.

## 1. Before any change

1. Read [docs/adr/README.md](docs/adr/README.md) and every ADR its "Which ADR covers what" table names for the area you will touch. Read [ADR 0001](docs/adr/0001-record-architecture-decisions.md) and [ADR 0002](docs/adr/0002-purpose-scope-and-use-cases.md) if you have not in this session.
2. State, before editing, which ADRs apply (number and the rule). Do the same in your commit message body when a change is non-trivial.
3. Read the code you will change. ADRs say what must hold; the code says how it holds today.

## 2. ADRs are followed strictly

- **Never contradict an accepted ADR.** If a request or an idea conflicts with one, **stop**, name the ADR and the rule, say what the request would change, and ask the owner whether to supersede it. Do not implement the conflicting behaviour first and mention it later. Do not reinterpret an ADR to make a change fit.
- **A decision change needs a new ADR**, written before or together with the code: next free number, Status `Accepted` only after the owner agrees, and the old ADR marked `Superseded by ADR NNNN`. Never edit an accepted ADR to say something different from what it decided. Fixing a wrong fact, a typo or a link is allowed.
- **Behaviour an ADR describes changes together with that ADR**, in the same commit: endpoints, tags written, statuses, thresholds, colours, widths, constants. Update [docs/adr/README.md](docs/adr/README.md) when you add or supersede an ADR.
- **Every feature maps to a use case** in ADR 0002. A feature without one needs an ADR that adds the use case first. Out-of-scope items in ADR 0002 are not built without superseding it.
- **Silence is not permission.** If no ADR covers a decision that matters (a new dependency, a new tag written, a new endpoint that writes, a new dialog, a new setting), write the ADR; do not decide it silently in code.
- If an ADR is wrong or stale against the code, report it to the owner and propose the fix; do not quietly follow the code.

## 3. Hard rules that come from the ADRs

- **Engine** (0004): never reimplement, reorder or skip `nzbfix` steps; never edit the discogs repository unless the owner asks, and then record why in an ADR.
- **Tags** (0004, 0014): UPPERCASE keys; never read a tag the tools wrote as input; never make a Discogs-owned tag editable and never overwrite a user-owned tag from automation. Keep `ALBUM_FIELDS`, `DISCOGS_FIXED` and `DISCOGS_PREFIXES` in sync with discogs `fixtags.py`.
- **Safety** (0007, 0008): every path goes through `safe()`; every endpoint that writes returns 409 while a job runs; never log, return or commit an API key; never add an endpoint that reads or writes outside `ROOT` or `INGEST_DIR`.
- **File names** (0010): `clean()` stays identical to discogs `bliss.clean()`; Tagwright never renames album folders.
- **Ingest** (0011): move only `fixed` albums; never overwrite or merge into an existing destination.
- **Status model** (0006, 0016): changing what makes a step done or partial is an ADR change.
- **Stack** (0005, 0029, 0034): single-file backend `app.py` (PEP 723 deps); frontend in `ui/` (Next.js static export, shadcn/ui). Tabs, single quotes. No new framework or build step without an ADR. Any change under `ui/` means `cd ui && npm run build` and committing the resulting `static/ui/`.
- **UI** (0030, 0031): colours keep their meaning; do not add a stats bar or filter tabs; the top bar navigation is the only filter; follow the dialog widths and fixed-width badge columns.

## 4. Verification (ADR 0018)

- Never run tests, servers or edits against `/path/to/staging`, the real ingest folder or any real library. Copy one album to a scratch directory, set `ROOT`, `INGEST_DIR` and `DATA_DIR` there, use a free port, and clean up afterwards.
- Check API behaviour with `curl`, tags and pictures on disk with `metaflac`, and the UI in a browser at 1440 px with a clean console. Report what you did **not** verify.
- Do not claim a feature works until you ran it. If something failed or was skipped, say so.
- Automated tests ([ADR 0035](docs/adr/0035-automated-tests-with-pytest.md)): `uv run --group test pytest`. They use synthetic albums in a temp directory and a fake `nzbfix`, never real data. A change to status, naming, job or move behaviour comes with a test that fails without it.

## 5. Related code

- Tag-management scripts live in `../discogs`; changes there must be confirmed against that project's ADRs.
- Use the `drcalc` binary from `../drcalc` as a replacement for `drmeter`.

## 6. Python

### Setup

- Python 3.14, modern syntax.
- Dependencies with `uv`: PEP 723 inline declaration and the `uv` shebang.
- Use the latest stable version of every dependency; check and update regularly.

### Tooling

- Ruff is the only linter and formatter. Do not install or run Black, isort or flake8.
- Always run Ruff through uv: `uv run ruff ...`.
- Config lives in `pyproject.toml`; the decision and its rules are in [ADR 0034](docs/adr/0034-python-formatting-and-linting-with-ruff.md). Do not modify `[tool.ruff]` unless the task is about tooling.
- If a lint rule seems wrong for the codebase, say so in your summary instead of disabling it.

### Workflow

After editing any Python file, run these in order on the files you changed:

1. `uv run ruff check --fix <changed files>`
2. `uv run ruff format <changed files>`
3. `uv run ruff check <changed files>` (must report zero errors)

- Format only the files you changed. Never run `uv run ruff format .` on the whole repo unless explicitly asked, because unrelated reformatting pollutes the diff.
- Do not use `--unsafe-fixes` unless asked.
- Never hand-format code to "look nicer". The formatter's output is final.

### Before marking done

- `uv run ruff check .` passes.
- `uv run ruff format --check .` passes (read-only; it does not rewrite files).

### Style

- Tabs, single quotes, line length 100: set in `pyproject.toml` ([ADR 0034](docs/adr/0034-python-formatting-and-linting-with-ruff.md)).
- Imports: stdlib, third-party, local, separated by blank lines. Ruff sorts them (rule set `I`); do not reorder by hand.
- No unused imports.
- f-strings, not `.format()` or `%`.
- Walrus operator (`:=`) only to bind a match result in a condition, e.g. `if m := re.match(...)`.

### Type annotations

Required for:

- all function signatures (every parameter and the return type)
- class attributes
- module-level variables, unless they are obvious primitives

Avoid `Any`. If it is genuinely necessary, add a comment saying why.

### Anti-patterns

- No bare `except:`. Catch specific errors: `except ValueError:` or `except (A, B):`.
- No `from module import *`.
- No `print()` for debug output. Use `logging.getLogger(__name__)`.
- No hardcoded credentials or connection strings. Use environment variables.
- No mutable default arguments: `def f(x: list = [])` is wrong; use `None` and create the list inside the function.

### Suppressions

- Do not add `# noqa`, `# fmt: off` or `# type: ignore` to silence a warning. Fix the underlying issue.
- If suppression is truly required, use the narrowest form (`# noqa: B008`, `# type: ignore[arg-type]`, never bare) and add a one-line reason.

## 7. Git (ADR 0020)

- **Never create a branch.** Work and commit directly on `main`, then push to `origin main`. `main` is the only branch; if any other exists, tell the owner. Do not tag unless asked.
- Never commit `data/`, `node_modules/`, `__pycache__/`, keys or music files.
- Keep commits focused, with a message that says what and why. Verify first ([ADR 0018](docs/adr/0018-verification.md)); there is no branch to catch a bad change.
- Never force-push or rewrite history.

## 8. Before you say "done"

Check each item and say which you checked:

- [ ] The ADRs I named at the start still hold, or the owner approved a superseding ADR.
- [ ] Changed behaviour, constants or endpoints are reflected in the ADRs and in the README index.
- [ ] `static/ui/` rebuilt (`cd ui && npm run build`) if anything under `ui/` changed.
- [ ] Verified on a copy, not on real data; what was not verified is stated.
- [ ] No secrets in code, logs, commits or output.
- [ ] `uv run --group test pytest` passes, or the failures are listed.
- [ ] Python changed: `uv run ruff check .` and `uv run ruff format --check .` pass, or the failures are listed.
