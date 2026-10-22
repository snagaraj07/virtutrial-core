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

Python 3.9 or newer is required. Runtime dependencies are listed in `requirements.txt`.

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

An unadjusted difference in means is reported beside it. A second contrast recalibrates the twin on the concurrent controls and subtracts that prediction from each treated patient's outcome.

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
├── requirements.txt
├── setup.py
├── src/
│   ├── __init__.py
│   ├── simulator.py       # synthetic trajectories and biomarker streams
│   ├── forecaster.py      # baseline digital-twin progression model
│   └── vca_engine.py      # virtual control arm comparison and power check
├── tests/
│   ├── test_simulator.py
│   └── test_vca.py
└── examples/
    └── autism_trial_demo.py
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
