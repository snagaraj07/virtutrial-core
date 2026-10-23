# Phase 2 — Data contract and loader

```yaml
id: "02"
status: complete
depends_on: ["01"]
```

## Goal

A researcher can point the library at a CSV or parquet file and get a frame that `DigitalTwinForecaster` and `VirtualControlArm` already accept.

## In scope

`src/schema.py`, one synthetic committed fixture, and loader tests. Wire `read_trajectories` so missing columns and duplicate patient-week keys fail with `TrajectorySchemaError`.

## Out of scope

Privacy-column refusal (phase 5), the CLI (phase 4), and any UI.

## Security

S1. The committed fixture uses only ids prefixed with `SYN-` and hand-written round numbers. Generate larger frames inside tests with `TrialSimulator` and `tmp_path`. Do not commit a dump of a real or realistic cohort.

## Deliverables

| Path | Purpose |
| --- | --- |
| `src/schema.py` | Contract, validation, CSV and parquet loader |
| `tests/fixtures/synthetic_trajectories.csv` | Two fake patients, weeks 0 and 1 |
| `tests/test_schema.py` | Accept, reject, and round-trip tests |
| `README.md` | Document the required columns and the loader |

## Steps

1. Add `schema.py` with the interfaces below. Reuse `COLUMNS` from `simulator.py` as the superset. Required columns are the list in Interfaces.
2. `read_trajectories` accepts `.csv` and `.parquet`. Any other suffix raises `TrajectorySchemaError`.
3. Validation checks: required columns present, `week` and `treated` numeric, one row per (`patient_id`, `week`), at least one week-0 row and one final-week row per patient, `treated` constant within a patient.
4. Write the fixture by hand, not by exporting a private file. Two patients, `SYN-001` and `SYN-002`, weeks 0 and 1, `treated` 0 and 1.
5. Tests cover a good simulator frame written to `tmp_path`, the committed fixture, a missing column, and a duplicate patient-week.
6. Document the contract in the README under a heading `Your own table`.

## Interfaces

```python
class TrajectorySchemaError(ValueError):
    """The table cannot be analyzed because it breaks the trajectory contract."""

REQUIRED_COLUMNS = (
    "patient_id",
    "week",
    "treated",
    "age",
    "baseline_score",
    "engagement_score",
    "gaze_fixation",
    "vocal_variability",
)

def validate_trajectories(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with the required columns and sorted patient_id, week."""

def read_trajectories(path: Path) -> pd.DataFrame:
    """Load a CSV or parquet file and validate it."""
```

`arm` may be absent. Do not require it.

## Tests

`tests/test_schema.py` uses `tmp_path` for generated files. Assert the committed fixture has four rows and both ids start with `SYN-`.

## Acceptance

```bash
ruff check .
pytest
python -c "from schema import read_trajectories; from pathlib import Path; frame = read_trajectories(Path('tests/fixtures/synthetic_trajectories.csv')); assert len(frame) == 4"
```

## Done when

The acceptance commands pass, the README names the required columns, and `manifest.json` marks phase 02 `complete` and phase 03, 04, and 05 `ready`.

## Do not

Do not add a network call. Do not accept Excel files in this phase. Do not log cell values in an exception message; name the column and the rule only.
