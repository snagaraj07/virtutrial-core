# Phase 3 — Reproducible package

```yaml
id: "03"
status: complete
depends_on: ["02"]
```

## Goal

A methods paper can name a version, and a later reader can install that version and rerun the fixture.

## In scope

`pyproject.toml` build metadata that matches `setup.py`, `CHANGELOG.md`, and `CITATION.cff`. Keep the import names `schema`, `simulator`, `forecaster`, and `vca_engine`.

## Out of scope

A new statistical method, the workbench, and publishing a release to PyPI. Tagging a release is a human action described in the changelog.

## Security

S1 and S3. Citation metadata contains the maintainer's GitHub login, not a private email. Do not add a token for publishing.

## Deliverables

| Path | Purpose |
| --- | --- |
| `pyproject.toml` | setuptools build backend and project version `0.1.0` |
| `CHANGELOG.md` | Keep-a-changelog sections for `0.1.0` |
| `CITATION.cff` | Citation file name `VirtuTrial Core` |
| `README.md` | Install remains `pip install -e ".[dev]"` and mentions the citation file |

## Steps

1. Add `pyproject.toml` with `setuptools.build_meta`. Point package discovery at the existing flat modules under `src/`. Do not rename imports.
2. If both `setup.py` and `pyproject.toml` would fight, keep a single source of version `0.1.0` and make the other read it. `src/__init__.py` `__version__` stays `0.1.0`.
3. Write `CHANGELOG.md` with `0.1.0` describing the simulator, forecaster, virtual control arm, loader, and contributor workflow.
4. Write `CITATION.cff` version 1.2.0, authors `Subramani Nagaraj`, repository `https://github.com/snagaraj07/virtutrial-core`, license MIT.
5. Confirm an editable install still imports `schema` and `simulator`.

## Interfaces

No new Python functions.

## Tests

The existing suite must pass after the packaging change.

## Acceptance

```bash
python -m pip install -e ".[dev]"
python - << 'PY'
import forecaster
import simulator
import vca_engine
from pathlib import Path
assert '__version__ = "0.1.0"' in Path("src/__init__.py").read_text()
PY
ruff check .
pytest
test -f CITATION.cff
test -f CHANGELOG.md
```

After phase 2, also import `schema` in that check. Do not add a package name that breaks `import simulator`.

## Done when

Acceptance passes and phase 03 is `complete` in `manifest.json`. Phase 09 stays `blocked` until phase 08 is complete.

## Do not

Do not publish to PyPI. Do not pin a private index URL.
