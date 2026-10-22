"""Tests for the digital twin and the virtual control arm."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from forecaster import DigitalTwinForecaster
from simulator import TrialSimulator, build_patient_table
from vca_engine import VirtualControlArm, estimate_power


def _endpoint_rmse(frame: pd.DataFrame, predicted: pd.DataFrame) -> float:
    actual = build_patient_table(frame)[["patient_id", "endpoint_score"]]
    merged = actual.merge(predicted, on="patient_id")
    error = merged["endpoint_score"].to_numpy() - merged["counterfactual"].to_numpy()
    return float(np.sqrt(np.mean(error ** 2)))


def test_forecaster_beats_predicting_the_training_mean():
    frame = TrialSimulator(seed=1).historical_controls(500)
    ids = frame["patient_id"].drop_duplicates().to_numpy()
    train = frame[frame["patient_id"].isin(set(ids[:400]))]
    held_out = frame[frame["patient_id"].isin(set(ids[400:]))]
    model = DigitalTwinForecaster().fit(train)
    predicted = model.predict_counterfactual(held_out)

    train_mean = build_patient_table(train)["endpoint_score"].mean()
    null = predicted.copy()
    null["counterfactual"] = train_mean

    assert model.n_patients_ == 400
    assert len(model.weeks_) == 12
    assert _endpoint_rmse(held_out, predicted) < _endpoint_rmse(held_out, null) * 0.8


def test_forecaster_refuses_a_treatment_only_cohort():
    trial = TrialSimulator(seed=0).trial(n_treatment=30, n_control=30)
    treated = trial.loc[trial["treated"] == 1]

    with pytest.raises(ValueError):
        DigitalTwinForecaster().fit(treated)


def test_prediction_before_fit_raises():
    trial = TrialSimulator(seed=0).trial(12, 12)

    with pytest.raises(RuntimeError):
        DigitalTwinForecaster().predict_counterfactual(trial)


def test_ancova_recovers_the_planted_effect_with_tighter_error():
    simulator = TrialSimulator(seed=8)
    history = simulator.historical_controls(400)
    trial = simulator.trial(n_treatment=180, n_control=180)
    predicted = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)
    result = VirtualControlArm().compare(trial, predicted)

    assert 4.0 < result.ancova_effect < 8.0
    assert result.ancova_se < result.unadjusted_se
    assert result.variance_reduction > 0.2
    assert result.ancova_p < 0.05


def test_missing_counterfactual_raises():
    trial = TrialSimulator(seed=0).trial(20, 20)
    history = TrialSimulator(seed=1).historical_controls(40)
    predicted = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)
    trimmed = predicted.iloc[:-3]

    with pytest.raises(ValueError):
        VirtualControlArm().compare(trial, trimmed)


def test_half_size_virtual_arm_has_the_smaller_standard_error():
    study = estimate_power(
        seed=7,
        n_sims=20,
        n_treatment=36,
        n_control=36,
        n_history=250,
    )

    assert study.n_control_reduced == 18
    assert study.reduced_vca_mean_se < study.reduced_unadjusted_mean_se * 0.85
    assert 0.0 <= study.reduced_vca_power <= 1.0
    assert np.isfinite(study.mean_variance_reduction)
