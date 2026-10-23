"""Tests for the reviewer diagnostics beside the treatment estimate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from diagnostics import baseline_comparison, follow_up, run_manifest, twin_check
from forecaster import FEATURES, RIDGE_ALPHAS, DigitalTwinForecaster
from simulator import SimulatorConfig, TrialSimulator


def test_baseline_comparison_is_near_zero_when_cohorts_share_a_process():
    simulator = TrialSimulator(seed=12)
    history = simulator.historical_controls(300)
    trial = simulator.trial(n_treatment=150, n_control=150)

    rows = baseline_comparison(history, trial)

    assert [row["feature"] for row in rows] == list(FEATURES)
    for row in rows:
        assert row["history_n"] == 300
        assert row["control_n"] == 150
        assert row["treatment_n"] == 150
        assert abs(row["smd"]) < 0.35
        assert row["history_sd"] > 0
    assert "patient_id" not in json.dumps(rows)


def test_baseline_comparison_flags_a_shifted_history():
    older = SimulatorConfig(age_min=12.0, age_max=17.0)
    younger = SimulatorConfig(age_min=3.0, age_max=8.0)
    history = TrialSimulator(config=older, seed=1).historical_controls(200)
    trial = TrialSimulator(config=younger, seed=2).trial(n_treatment=60, n_control=60)

    rows = {row["feature"]: row for row in baseline_comparison(history, trial)}

    assert rows["age"]["smd"] < -1.0


def test_twin_check_reports_error_on_concurrent_controls_only():
    simulator = TrialSimulator(seed=5)
    history = simulator.historical_controls(200)
    trial = simulator.trial(n_treatment=40, n_control=30)
    counterfactuals = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)

    check = twin_check(trial, counterfactuals)

    assert check["n_controls"] == 30
    assert check["rmse"] < check["observed_sd"]
    assert abs(check["mean_error"]) < check["rmse"]
    assert 0.5 < check["correlation"] <= 1.0
    assert set(check) == {"n_controls", "rmse", "mean_error", "observed_sd", "correlation"}


def test_twin_check_refuses_a_missing_control_prediction():
    simulator = TrialSimulator(seed=5)
    history = simulator.historical_controls(40)
    trial = simulator.trial(n_treatment=10, n_control=10)
    counterfactuals = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)

    with pytest.raises(ValueError):
        twin_check(trial, counterfactuals.iloc[:-1])


def test_run_manifest_hashes_the_input_bytes(tmp_path: Path):
    simulator = TrialSimulator(seed=9)
    history = simulator.historical_controls(30)
    trial = simulator.trial(n_treatment=10, n_control=10)
    history_path = tmp_path / "history.csv"
    trial_path = tmp_path / "trial.csv"
    history.to_csv(history_path, index=False)
    trial.to_csv(trial_path, index=False)
    forecaster = DigitalTwinForecaster().fit(history)

    manifest = run_manifest(history_path, trial_path, forecaster)

    history_digest = hashlib.sha256(history_path.read_bytes()).hexdigest()
    trial_digest = hashlib.sha256(trial_path.read_bytes()).hexdigest()
    assert manifest["history_file"]["sha256"] == history_digest
    assert manifest["trial_file"]["sha256"] == trial_digest
    assert manifest["features"] == list(FEATURES)
    assert manifest["estimator"] == "StandardScaler + RidgeCV"
    assert manifest["ridge_alpha"] in RIDGE_ALPHAS
    assert manifest["ridge_tuned"] is True
    assert manifest["random_seed"] is None
    assert manifest["n_training_controls"] == 30
    assert manifest["weeks_fit"] == list(range(12))
    assert manifest["created_at"].endswith("+00:00")
    assert set(manifest["software"]) == {"python", "numpy", "pandas", "scikit_learn", "scipy"}
    assert "patient_id" not in json.dumps(manifest)


def test_follow_up_counts_a_dropout_and_a_missed_visit():
    simulator = TrialSimulator(seed=3)
    history = simulator.historical_controls(20)
    trial = simulator.trial(n_treatment=8, n_control=8)
    dropped = trial["patient_id"].iloc[0]
    trial = trial.loc[~((trial["patient_id"] == dropped) & (trial["week"] == trial["week"].max()))]
    skipped = trial["patient_id"].iloc[-1]
    trial = trial.loc[~((trial["patient_id"] == skipped) & (trial["week"] == 3))]

    summary = follow_up(history, trial)

    assert summary["n_dropouts"] == 1
    assert summary["n_completers"] == 15
    assert summary["n_missed_visits"] == 2
    assert summary["analysis_set"] == "completers"
    assert summary["endpoint"]["name"] == "engagement_score"
    assert "patient_id" not in json.dumps(summary)
