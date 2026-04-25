# Contributing to FrostWatch

Thank you for considering a contribution. FrostWatch welcomes bug reports, documentation improvements, new features, and code reviews.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Getting started](#getting-started)
- [Development setup](#development-setup)
- [Commit conventions](#commit-conventions)
- [Pull request process](#pull-request-process)
- [Testing](#testing)

---

## Code of conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Report unacceptable behaviour to arunrajiah@gmail.com.

---

## Getting started

1. Check existing issues before opening a new one.
2. For large changes, open an issue first to discuss the approach.
3. For small fixes (typos, docs, minor bugs), open a PR directly.

---

## Development setup

**Prerequisites:** Python 3.11+, Node.js 20+

```bash
git clone https://github.com/arunrajiah/frostwatch.git
cd frostwatch

# Python — editable install with dev extras
pip install -e ".[dev]"

# Frontend
cd frontend && npm install && cd ..
```

**Run the stack locally:**

```bash
# Terminal 1 — backend with auto-reload
frostwatch config init
frostwatch serve --reload

# Terminal 2 — frontend dev server (proxies /api → :8000)
cd frontend && npm run dev
```

Open http://localhost:5173.

---

## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`

Examples:
```
feat(analysis): add partition pruning detection
fix(scheduler): prevent duplicate sync jobs on rapid config reload
docs(readme): add Kubernetes deployment example
```

The PR title must follow this format — CI enforces it.

---

## Pull request process

1. Fork and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make focused, atomic commits.
3. Run the full check suite locally (see [Testing](#testing)).
4. Open a PR against `main` and fill in the PR template.
5. At least one maintainer approval is required to merge.
6. We squash-merge to keep a clean linear history.

### PR size guidelines

| Label | Lines changed |
|-------|--------------|
| `size/XS` | < 10 |
| `size/S`  | 10–99 |
| `size/M`  | 100–499 |
| `size/L`  | 500–999 |
| `size/XL` | 1000+ — consider splitting |

---

## Testing

```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=frostwatch --cov-report=term-missing

# Lint
ruff check frostwatch/
ruff format --check frostwatch/

# Type check
mypy frostwatch/

# Frontend type check + build
cd frontend && npm run build
```

Tests live in `tests/unit/`. Mirror the package structure. Integration tests (requiring real Snowflake credentials) go in `tests/integration/` and are skipped in CI by default.
