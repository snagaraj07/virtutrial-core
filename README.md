# VirtuTrial Core

VirtuTrial is an open-source Python framework for building a synthetic control arm and checking a digital-twin forecast against a randomized comparison. Researchers can simulate a longitudinal trial, train a baseline progression model on historical controls, and estimate a treatment effect with a smaller concurrent control arm.

The included endpoint is a synthetic functional engagement score inspired by an autism-trial setting, along with gaze-fixation and vocal-variability streams. Higher engagement is better. These series are generated for method development. VirtuTrial is research software: diagnosis, treatment, and trial decisions stay with qualified professionals and studies that were designed and validated for that purpose.

The demo draws the historical cohort and the trial from the same synthetic process. That is the setting where a baseline twin transfers cleanly. A twin trained on a mismatched population will explain less of the outcome, and the precision gain shrinks with it.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.9 or newer is required. Runtime dependencies are listed in `requirements.txt`. Cite the software with [CITATION.cff](CITATION.cff). The version history is in [CHANGELOG.md](CHANGELOG.md).

## Quick start

```python
from simulator import TrialSimulator
from forecaster import DigitalTwinForecaster
from vca_engine import VirtualControlArm

sim = TrialSimulator(seed=7)
history = sim.historical_controls(400)
trial = sim.trial(n_treatment=60, n_control=30)

twin = DigitalTwinForecaster().fit(history)
counterfactuals = twin.predict_counterfactual(trial)
result = VirtualControlArm().compare(trial, counterfactuals)
print(result.summary())
```

`DigitalTwinForecaster` uses pre-treatment measurements only: age, baseline score, gaze fixation, and vocal variability at week 0. It forecasts the weekly path expected if that patient followed the control process. The virtual control arm's primary estimate is the treatment coefficient from

```text
final engagement ~ treated + predicted control outcome
```

Three comparisons are reported beside it. An unadjusted difference in means. An ANCOVA on the week-0 `baseline_score` alone, so a reader can see what the twin's extra measurements added. And a contrast that recalibrates the twin on the concurrent controls and subtracts that prediction from each treated patient's outcome.

## Diagnostics for a methods reviewer

`runner.run_study` and the workbench results page include three checks from `diagnostics.py`. All of them are aggregates.

- **Baseline characteristics.** Week-0 mean and SD of each twin input for historical controls, concurrent controls, and the treatment arm, with the standardized mean difference between the two control groups. A twin trained on patients who differ from the trial's untreated arm explains less of the outcome.
- **Twin check on concurrent controls.** Concurrent controls are untreated, so their observed final score is what the twin claims to forecast. The report gives RMSE, mean error (observed minus predicted), the observed SD, and the correlation on those patients.
- **Run record.** SHA-256 and byte count of both input files, the feature list, the estimator and its penalty, the weeks the twin was fit on, the training cohort size, and the Python, numpy, pandas, scikit-learn, and scipy versions. The default ridge fit draws no random numbers, so `random_seed` is null.

The twin's prediction enters the ANCOVA as a fixed covariate. With randomization that keeps the treatment coefficient unbiased. The analytic standard error still treats the forecast as known. `run_study` also reports a patient-resampled bootstrap standard error and interval that refits the twin on each replicate. The twin check on concurrent controls is the place to judge whether the forecast is good enough to lean on.

The ridge penalty is chosen by leave-one-out search over `0.1`, `1`, `10`, and `100` unless you pass `DigitalTwinForecaster(tune=False)` or your own estimator.

## Follow-up and the endpoint

`week` is the scheduled visit number. Week 0 is required. A missing later row is a missed visit. A patient without the last scheduled week is a dropout. The primary analysis uses completers only. It does not carry the last observation forward.

The column `engagement_score` is a synthetic stand-in for a functional endpoint, higher is better. A study replaces it with a validated instrument and keeps the same column name and visit numbering. VirtuTrial does not define a clinical scale, a visit window in days, or a regulatory endpoint.

## Your own table

`read_trajectories` loads a `.csv` or `.parquet` file. Every patient needs a week-0 row. Later weeks may be missing. `treated` stays 0 or 1 for that patient across weeks. One row per patient and week.

| Column | Meaning |
| --- | --- |
| `patient_id` | Row key. The committed fixture uses `SYN-` ids only. |
| `week` | Visit number. Week 0 is the pre-treatment baseline. |
| `treated` | `0` for a control patient, `1` for a treated patient. |
| `age` | Age in years at baseline. |
| `baseline_score` | Baseline value of the endpoint. |
| `engagement_score` | Endpoint at that week. Higher is better. |
| `gaze_fixation` | Week-0 gaze measurement used by the twin. Later weeks can repeat it. |
| `vocal_variability` | Week-0 vocal measurement used by the twin. |

`arm` is optional. The loader then refuses identifier-like column names (`name`, `mrn`, `email`, `note`, and the other tokens in `privacy.py`) and two value patterns: an email address, and a `###-##-####` number. The gate does not make a file lawful to use, and it does not scrub identifiers hidden inside an allowed column. Keep real study files outside git.

## Local workbench

The workbench is server-rendered HTML. It uses the browser's built-in controls, a stylesheet shipped with the app, and no external fonts or scripts. It listens on this computer only.

```bash
pip install -e ".[workbench]"
python -m workbench
```

Open http://127.0.0.1:8000 . Choose a historical-control file and a trial file. Two synthetic files are included for that first run:

- `examples/historical_controls.csv` — 20 untreated patients
- `examples/trial.csv` — 12 treated patients and 10 concurrent controls

Both come from `TrialSimulator` with seed 21. The ids are `H`, `T`, and `C` plus a number. They are not study records. The results page shows the aggregate estimate. Patient-level predictions stay in the local data directory, which defaults to `.local-data/` and is not part of git.

`VIRTUTRIAL_MODE` defaults to `local`. Local mode has no login screen and records audit events as `local-operator`.

Hosted mode is for several people behind an identity provider. It refuses to start unless all three are set:

```bash
export VIRTUTRIAL_MODE=hosted
export VIRTUTRIAL_OIDC_ISSUER=https://issuer.example
export VIRTUTRIAL_OIDC_CLIENT_ID=...
export VIRTUTRIAL_OIDC_CLIENT_SECRET=...
```

Study routes then require `Authorization: Bearer <token>`. Roles are `analyst` (upload and run), `admin` (also delete), and `auditor` (read results and the audit log, not patient-level predictions). The client secret is never written to `report.json` or the audit file. A real identity-provider tenant is not bundled; tests inject a fake verifier. Hosted mode is not certified for any regulation.

```python
from pathlib import Path
from schema import read_trajectories

frame = read_trajectories(Path("history.csv"))
```

## Demo

```bash
python examples/autism_trial_demo.py
python examples/autism_trial_demo.py --sims 200
```

The script prints one simulated trial, then a Monte Carlo comparison:

- a traditional difference in means with the full concurrent control arm
- the same unadjusted comparison after that control arm is cut in half
- a virtual control arm (ANCOVA on the twin's prediction) that uses the half-size control arm and a twin trained on historical controls

The historical cohort is the source of the extra precision. On the default 100-simulation run, with a planted 6-point effect, the unadjusted comparison using 40 concurrent controls has about 49% power. The virtual control arm using 20 concurrent controls and 400 historical controls has about 88% power. The script states whether that relationship holds for the run you just executed. The single trial printed above those rates is one draw, so its unadjusted p-value can miss the planted effect while the adjusted estimate recovers it.

## Layout

```text
virtutrial-core/
├── LICENSE
├── README.md
├── CITATION.cff
├── CHANGELOG.md
├── pyproject.toml
├── requirements.txt
├── setup.py
├── src/
│   ├── __init__.py
│   ├── simulator.py       # synthetic trajectories and biomarker streams
│   ├── forecaster.py      # baseline digital-twin progression model
│   ├── vca_engine.py      # virtual control arm comparison and power check
│   ├── schema.py          # table contract and loader
│   ├── privacy.py         # refusal check for identifier columns
│   ├── diagnostics.py     # baseline comparison, twin check, run manifest
│   ├── runner.py          # one run, writes report.json
│   ├── workbench.py       # local or hosted server-rendered UI
│   ├── auth.py            # OIDC settings and token verifier
│   ├── audit.py           # append-only JSONL audit log
│   └── studies.py         # study delete that leaves the audit intact
├── tests/
│   ├── test_simulator.py
│   ├── test_vca.py
│   ├── test_schema.py
│   ├── test_privacy.py
│   ├── test_diagnostics.py
│   ├── test_runner.py
│   └── test_workbench.py
└── examples/
    ├── autism_trial_demo.py
    ├── historical_controls.csv
    └── trial.csv
```

The default forecaster is a standardized ridge regression with one output per week. Pass any scikit-learn regressor that accepts a two-dimensional target to `DigitalTwinForecaster(estimator=...)` when you want a different progression model.

## Tests

```bash
ruff check .
pytest
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. The conduct rules are in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities through the private advisory path in [SECURITY.md](SECURITY.md).

## Real study tables

This repository holds the statistical library and synthetic fixtures. A deployment that analyzes someone else's trial tables is specified in [agent-plan/00-system-design.md](agent-plan/00-system-design.md). Study files, credentials, and patient-level outputs stay outside git. Build agents follow [agent-plan/README.md](agent-plan/README.md) one phase at a time.

## License

MIT. See [LICENSE](LICENSE).
