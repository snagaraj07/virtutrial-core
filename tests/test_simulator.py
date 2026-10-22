"""Tests for the synthetic trajectory generator."""

from __future__ import annotations

import numpy as np
import pandas as pd

from simulator import COLUMNS, TrialSimulator


def test_trial_has_a_row_for_every_patient_week():
    frame = TrialSimulator(seed=3).trial(n_treatment=6, n_control=4)

    assert list(frame.columns) == list(COLUMNS)
    assert frame["week"].nunique() == 12
    assert len(frame) == 10 * 12
    assert frame.groupby("patient_id")["week"].nunique().eq(12).all()
    assert set(frame["arm"]) == {"treatment", "control"}
    assert frame.loc[frame["arm"] == "treatment", "treated"].eq(1).all()
    assert frame.loc[frame["arm"] == "control", "treated"].eq(0).all()


def test_scores_stay_inside_the_synthetic_bounds():
    frame = TrialSimulator(seed=4).historical_controls(25)

    assert frame["engagement_score"].between(0, 100).all()
    assert frame["gaze_fixation"].between(0, 1).all()
    assert (frame["vocal_variability"] > 0).all()
    assert (frame["arm"] == "historical_control").all()
    assert frame["treated"].eq(0).all()


def test_same_seed_reproduces_the_trial():
    first = TrialSimulator(seed=9).trial(8, 8)
    second = TrialSimulator(seed=9).trial(8, 8)

    pd.testing.assert_frame_equal(first, second)


def test_planted_treatment_effect_raises_the_final_score():
    frame = TrialSimulator(seed=2).trial(n_treatment=400, n_control=400)
    final = frame.loc[frame["week"] == 11]
    treated = final.loc[final["treated"] == 1, "engagement_score"].mean()
    control = final.loc[final["treated"] == 0, "engagement_score"].mean()

    assert treated - control > 4.0
    assert np.isfinite(treated)


def test_week_zero_is_still_baseline_for_both_arms():
    frame = TrialSimulator(seed=5).trial(n_treatment=300, n_control=300)
    baseline = frame.loc[frame["week"] == 0]
    treated = baseline.loc[baseline["treated"] == 1, "engagement_score"].mean()
    control = baseline.loc[baseline["treated"] == 0, "engagement_score"].mean()

    assert abs(treated - control) < 1.5
