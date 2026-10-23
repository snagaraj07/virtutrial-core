"""Checks a methods reviewer reads beside the treatment estimate.

Three questions come up before anyone trusts a virtual control arm:

1. Do the historical patients resemble the concurrent controls at baseline?
2. How well does the twin forecast the patients whose untreated outcome is
   observed, the concurrent controls?
3. Exactly what ran, on exactly which files?

Every value here is an aggregate. No function returns a patient_id.
"""

from __future__ import annotations

import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

from forecaster import FEATURES, MIN_CONTROLS, DigitalTwinForecaster
from simulator import build_patient_table

ROUND = 4
ENDPOINT = {
    "name": "engagement_score",
    "direction": "higher_is_better",
    "kind": "synthetic",
    "label": "Functional engagement score (synthetic stand-in)",
}


def baseline_comparison(history: pd.DataFrame, trial: pd.DataFrame) -> list[dict]:
    """Week-0 mean and SD of each twin feature in the three patient groups.

    ``smd`` is the standardized mean difference between the concurrent
    controls and the historical controls, using the pooled SD of those two
    groups. Values near zero mean the twin was trained on patients who look
    like the trial's untreated arm.
    """

    history_rows = _first_week(history)
    history_rows = history_rows.loc[history_rows["treated"] == 0]
    trial_rows = _first_week(trial)
    controls = trial_rows.loc[trial_rows["treated"] == 0]
    treated = trial_rows.loc[trial_rows["treated"] == 1]

    rows = []
    for feature in FEATURES:
        history_mean, history_sd = _moments(history_rows[feature])
        control_mean, control_sd = _moments(controls[feature])
        treatment_mean, treatment_sd = _moments(treated[feature])
        pooled = float(np.sqrt((history_sd**2 + control_sd**2) / 2.0))
        smd = (control_mean - history_mean) / pooled if pooled > 0 else 0.0
        rows.append(
            {
                "feature": feature,
                "history_n": int(len(history_rows)),
                "history_mean": round(history_mean, ROUND),
                "history_sd": round(history_sd, ROUND),
                "control_n": int(len(controls)),
                "control_mean": round(control_mean, ROUND),
                "control_sd": round(control_sd, ROUND),
                "treatment_n": int(len(treated)),
                "treatment_mean": round(treatment_mean, ROUND),
                "treatment_sd": round(treatment_sd, ROUND),
                "smd": round(float(smd), ROUND),
            }
        )
    return rows


def twin_check(trial: pd.DataFrame, counterfactuals: pd.DataFrame) -> dict:
    """Forecast error of the twin on the concurrent controls.

    Those patients are untreated, so their observed final-week score is the
    quantity the twin claims to predict. ``mean_error`` is observed minus
    predicted; a positive value means the twin forecasts too low.
    """

    patients = build_patient_table(trial)
    controls = patients.loc[patients["treated"] == 0]
    merged = controls.merge(
        counterfactuals.loc[:, ["patient_id", "counterfactual"]], on="patient_id", how="inner"
    )
    if len(merged) != len(controls):
        raise ValueError("Every concurrent control needs a counterfactual prediction.")

    observed = merged["endpoint_score"].to_numpy(dtype=float)
    predicted = merged["counterfactual"].to_numpy(dtype=float)
    error = observed - predicted
    n = int(len(error))
    correlation = None
    if n >= 3 and np.std(observed) > 0 and np.std(predicted) > 0:
        correlation = round(float(np.corrcoef(observed, predicted)[0, 1]), ROUND)

    observed_sd = float(observed.std(ddof=1)) if n >= 2 else 0.0
    return {
        "n_controls": n,
        "rmse": round(float(np.sqrt(np.mean(error**2))), ROUND) if n else None,
        "mean_error": round(float(error.mean()), ROUND) if n else None,
        "observed_sd": round(observed_sd, ROUND),
        "correlation": correlation,
    }


def follow_up(history: pd.DataFrame, trial: pd.DataFrame) -> dict:
    """Visit schedule, missed visits, and dropout counts.

    ``week`` is the scheduled visit number. A missing row is a missed visit.
    A patient without the last scheduled week is a dropout. The primary
    analysis uses completers only. This is not last-observation-carried-forward.
    """

    history_weeks = [int(week) for week in sorted(history["week"].unique())]
    trial_weeks = [int(week) for week in sorted(trial["week"].unique())]
    final_week = trial_weeks[-1] if trial_weeks else 0
    trial_patients = int(trial["patient_id"].nunique())
    history_patients = int(history.loc[history["treated"] == 0, "patient_id"].nunique())
    trial_completers = int(trial.loc[trial["week"] == final_week, "patient_id"].nunique())
    history_final = history_weeks[-1] if history_weeks else 0
    history_completers = int(
        history.loc[
            (history["treated"] == 0) & (history["week"] == history_final), "patient_id"
        ].nunique()
    )
    expected_trial = trial_patients * len(trial_weeks)
    return {
        "scheduled_weeks": trial_weeks,
        "final_week": final_week,
        "n_randomized": trial_patients,
        "n_completers": trial_completers,
        "n_dropouts": trial_patients - trial_completers,
        "n_missed_visits": int(expected_trial - len(trial)),
        "history_n": history_patients,
        "history_n_completers": history_completers,
        "analysis_set": "completers",
        "endpoint": dict(ENDPOINT),
    }


def run_manifest(
    history_path: Path, trial_path: Path, forecaster: DigitalTwinForecaster
) -> dict:
    """What ran, on which bytes, with which software.

    A closed-form ridge fit draws no random numbers, so ``random_seed`` is
    null unless a bootstrap or a sampling estimator is used.
    """

    model = forecaster.pipeline.named_steps["model"]
    return {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "history_file": {
            "sha256": _sha256(history_path),
            "bytes": int(Path(history_path).stat().st_size),
        },
        "trial_file": {
            "sha256": _sha256(trial_path),
            "bytes": int(Path(trial_path).stat().st_size),
        },
        "features": list(FEATURES),
        "estimator": f"StandardScaler + {type(model).__name__}",
        "ridge_alpha": float(forecaster.alpha_),
        "ridge_tuned": bool(forecaster.tune),
        "n_incomplete_dropped": int(forecaster.n_incomplete_dropped_),
        "random_seed": None,
        "min_training_controls": int(MIN_CONTROLS),
        "n_training_controls": int(forecaster.n_patients_),
        "weeks_fit": [int(week) for week in forecaster.weeks_],
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "scipy": scipy.__version__,
        },
    }


def _first_week(frame: pd.DataFrame) -> pd.DataFrame:
    required = ("patient_id", "week", "treated", *FEATURES)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    first = int(frame["week"].min())
    return (
        frame.loc[frame["week"] == first, list(required)]
        .drop_duplicates("patient_id")
        .reset_index(drop=True)
    )


def _moments(values: pd.Series) -> tuple[float, float]:
    numbers = values.to_numpy(dtype=float)
    if len(numbers) == 0:
        return 0.0, 0.0
    mean = float(numbers.mean())
    sd = float(numbers.std(ddof=1)) if len(numbers) > 1 else 0.0
    return mean, sd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
