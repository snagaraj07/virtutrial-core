# Contributing to VirtuTrial Core

VirtuTrial is research software for synthetic control arms. Changes land through a pull request. The default branch accepts a pull request only after the test workflow is green.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

Python 3.9 or newer. The CI workflow runs 3.9 and 3.12.

## What to change

| Kind of change | Where it goes | Test it with |
| --- | --- | --- |
| Synthetic trajectories | `src/simulator.py` | `tests/test_simulator.py` |
| Baseline progression model | `src/forecaster.py` | `tests/test_vca.py` |
| Treatment comparison | `src/vca_engine.py` | `tests/test_vca.py` |
| Docs, templates, CI | the matching file | the acceptance check in that phase, or `ruff` and `pytest` |

A new progression model should be a scikit-learn regressor passed to `DigitalTwinForecaster(estimator=...)`. It must accept a two-dimensional target, one column per week.

The primary estimand is the treatment coefficient in `final engagement ~ treated + predicted control outcome`. A pull request that changes that estimand needs a simulator test that reports bias or variance, not only a shape check.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep the patch limited to one change.
3. Run `ruff check .` and `pytest`.
4. Fill in the pull request template.
5. Confirm the diff has no study tables, patient-level output, credentials, or secrets.

Issues use the bug and change-request forms. Security reports use the private advisory link in [SECURITY.md](SECURITY.md).

## Conduct and build plan

Participation follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

The real-data workbench is not part of the library yet. Agents and contributors who build it follow [agent-plan/README.md](agent-plan/README.md), one phase at a time, under [agent-plan/01-security-invariants.md](agent-plan/01-security-invariants.md).
