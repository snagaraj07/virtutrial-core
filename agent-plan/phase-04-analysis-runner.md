# Phase 4 — Analysis runner

```yaml
id: "04"
status: blocked
depends_on: ["02"]
```

## Goal

One command reads a historical-control file and a trial file and writes an aggregate report plus a patient-level prediction file.

## In scope

`src/runner.py`, a `python -m runner` entry, and tests that use temporary directories.

## Out of scope

The privacy gate, the UI, and hosted storage. Phase 5 will call the runner only after the gate passes. This phase may call `read_trajectories` directly in tests.

## Security

S1 and S5. `report.json` contains aggregate numbers only. `counterfactuals.csv` contains `patient_id` and `counterfactual` and is written beside the report. Tests use `tmp_path`. The runner creates no network connection.

## Deliverables

| Path | Purpose |
| --- | --- |
| `src/runner.py` | `run_study` and the CLI |
| `tests/test_runner.py` | Report keys, no extra row dumps inside `report.json` |

## Steps

1. Implement `run_study(history_path, trial_path, output_dir) -> dict`.
2. Load both files with `read_trajectories`.
3. Fit `DigitalTwinForecaster` on rows with `treated == 0` from the history file. Raise `TrajectorySchemaError` when fewer than 10 control patients are present. The forecaster already enforces `MIN_CONTROLS`.
4. Predict counterfactuals for the trial and call `VirtualControlArm.compare`.
5. Write `output_dir/report.json` with the keys in Interfaces. Include mean engagement by week and arm, rounded to 4 decimal places.
6. Write `output_dir/counterfactuals.csv` with columns `patient_id` and `counterfactual` only.
7. CLI: `python -m runner --history PATH --trial PATH --output DIR`.
8. Register the module so `python -m runner` works from an editable install. A `runner.py` under `src/` matches the other modules.

## Interfaces

`report.json` keys, all required:

```text
schema_version          integer 1
library_version         string from src/__init__.py
n_history_controls      integer
n_treatment             integer
n_control               integer
planted_effect          null for external files
unadjusted_effect       number
unadjusted_se           number
unadjusted_p            number
ancova_effect           number
ancova_se               number
ancova_p                number
counterfactual_effect   number
counterfactual_se       number
counterfactual_p        number
outcome_sd              number
residual_sd             number
variance_reduction      number
mean_engagement         list of {arm, week, mean}
```

`report.json` must not contain `patient_id` or per-patient scores.

## Tests

Build history and trial CSVs with `TrialSimulator` into `tmp_path`. Assert the report keys, assert `patient_id` is absent from the JSON text, and assert the CSV has one row per trial patient.

## Acceptance

```bash
ruff check .
pytest tests/test_runner.py
pytest
```

## Done when

Acceptance passes and phase 04 is `complete`. Leave phase 06 `blocked` until phase 05 is also complete.

## Do not

Do not put raw rows in `report.json`. Do not add an upload endpoint in this phase. Do not call an external service.
