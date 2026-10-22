"""Baseline digital-twin progression model.

The default engine is a regularized multi-output linear model. It maps
pre-treatment age, baseline score, gaze fixation, and vocal variability to
the weekly engagement path expected under control. ``estimator`` can be any
scikit-learn regressor that accepts a two-dimensional target, so a neural
sequence model can replace the default later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ("age", "baseline_score", "gaze_fixation", "vocal_variability")
MIN_CONTROLS = 10


class DigitalTwinForecaster:
    """Forecast the untreated trajectory from baseline measurements."""

    def __init__(self, alpha: float = 1.0, estimator=None) -> None:
        self.alpha = alpha
        model = Ridge(alpha=alpha) if estimator is None else estimator
        self.pipeline = Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", model),
            ]
        )
        self._fitted = False
        self.n_patients_ = 0
        self.weeks_: list[int] = []

    def fit(self, frame: pd.DataFrame, controls_only: bool = True) -> "DigitalTwinForecaster":
        """Fit on complete trajectories. Training defaults to untreated patients."""

        baseline = _baseline_rows(frame)
        if controls_only:
            baseline = baseline.loc[baseline["treated"] == 0].reset_index(drop=True)
        if len(baseline) < MIN_CONTROLS:
            raise ValueError(
                f"Need at least {MIN_CONTROLS} control patients with complete "
                "trajectories to fit the digital twin."
            )

        trajectory, weeks = _trajectory_matrix(frame, baseline["patient_id"])
        self.pipeline.fit(baseline.loc[:, FEATURES], trajectory)
        self._fitted = True
        self.n_patients_ = int(len(baseline))
        self.weeks_ = weeks
        return self

    def predict_trajectory(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predicted engagement at every trained week, one row per patient-week."""

        predicted, patient_ids = self._predict_matrix(frame)
        n_weeks = predicted.shape[1]
        return pd.DataFrame(
            {
                "patient_id": np.repeat(patient_ids, n_weeks),
                "week": np.tile(np.asarray(self.weeks_, dtype=int), len(patient_ids)),
                "predicted_engagement": predicted.reshape(-1),
            }
        )

    def predict_counterfactual(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predicted final-week engagement if the patient stayed on the control path."""

        predicted, patient_ids = self._predict_matrix(frame)
        return pd.DataFrame(
            {
                "patient_id": patient_ids,
                "counterfactual": predicted[:, -1],
            }
        )

    def _predict_matrix(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        if not self._fitted:
            raise RuntimeError("Fit the digital twin on historical controls before predicting.")
        baseline = _baseline_rows(frame)
        predicted = np.asarray(
            self.pipeline.predict(baseline.loc[:, FEATURES]),
            dtype=float,
        )
        if predicted.ndim == 1:
            predicted = predicted.reshape(-1, 1)
        if predicted.shape[1] != len(self.weeks_):
            raise ValueError(
                "The stand-in estimator returned a different number of weeks than it was fit on."
            )
        return predicted, baseline["patient_id"].to_numpy()


def _baseline_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = ("patient_id", "week", "treated", *FEATURES)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("The trajectory frame is empty.")

    baseline_week = int(frame["week"].min())
    rows = (
        frame.loc[frame["week"] == baseline_week, list(required)]
        .drop_duplicates("patient_id")
        .reset_index(drop=True)
    )
    if rows.empty:
        raise ValueError("No baseline rows are available for forecasting.")
    return rows


def _trajectory_matrix(
    frame: pd.DataFrame, patient_ids: pd.Series
) -> tuple[np.ndarray, list[int]]:
    wide = frame.pivot_table(
        index="patient_id",
        columns="week",
        values="engagement_score",
        aggfunc="mean",
    )
    weeks = [int(week) for week in sorted(wide.columns)]
    wide = wide.reindex(index=patient_ids.tolist(), columns=weeks)
    if wide.isna().any().any():
        raise ValueError("Every training patient needs an engagement score at every week.")
    return wide.to_numpy(dtype=float), weeks
