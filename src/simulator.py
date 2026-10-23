"""Synthetic longitudinal trial trajectories.

The endpoint is a made-up functional engagement score: higher is better.
Gaze fixation and vocal variability are baseline-correlated biomarker
streams for method development. They are not clinical instruments, and the
rows are not patient records.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COLUMNS = (
    "patient_id",
    "arm",
    "treated",
    "week",
    "age",
    "baseline_score",
    "engagement_score",
    "gaze_fixation",
    "vocal_variability",
)


@dataclass(frozen=True)
class SimulatorConfig:
    """Parameters of the synthetic data-generating process."""

    n_weeks: int = 12
    baseline_mean: float = 55.0
    baseline_sd: float = 10.0
    age_min: float = 3.0
    age_max: float = 17.0
    treatment_effect: float = 6.0
    innovation_sd: float = 2.0
    natural_weekly_change: float = 0.12

    def __post_init__(self) -> None:
        if self.n_weeks < 2:
            raise ValueError("n_weeks must be at least 2.")
        if self.baseline_sd <= 0 or self.innovation_sd <= 0:
            raise ValueError("Standard deviations must be positive.")
        if self.age_min >= self.age_max:
            raise ValueError("age_min must be below age_max.")
        if self.treatment_effect < 0:
            raise ValueError("treatment_effect is an improvement and must be >= 0.")


class TrialSimulator:
    """Generate historical controls and a randomized trial from one process.

    Week 0 is the pre-treatment baseline. A planted improvement then grows
    linearly through the final week in the treatment arm only. Historical
    controls and concurrent controls share that untreated process, so a twin
    fit on history is transferable in this simulation.
    """

    def __init__(self, config: SimulatorConfig | None = None, seed: int = 0) -> None:
        self.config = config or SimulatorConfig()
        self._rng = np.random.default_rng(seed)
        self._next_id = 1

    def historical_controls(self, n: int) -> pd.DataFrame:
        """Return ``n`` untreated patients observed for every week."""

        return self._cohort(n, arm="historical_control", treated=False, id_prefix="H")

    def trial(self, n_treatment: int, n_control: int) -> pd.DataFrame:
        """Return a randomized trial with concurrent controls."""

        if n_control < 1:
            raise ValueError("n_control must be at least 1.")
        treated = self._cohort(n_treatment, arm="treatment", treated=True, id_prefix="T")
        control = self._cohort(n_control, arm="control", treated=False, id_prefix="C")
        return pd.concat([treated, control], ignore_index=True)

    def _cohort(self, n: int, arm: str, treated: bool, id_prefix: str) -> pd.DataFrame:
        if n < 1:
            raise ValueError("Cohort size must be at least 1.")

        config = self.config
        rng = self._rng
        n_weeks = config.n_weeks
        age = rng.uniform(config.age_min, config.age_max, size=n)
        baseline = np.clip(
            rng.normal(config.baseline_mean, config.baseline_sd, size=n),
            5.0,
            95.0,
        )
        weeks = np.arange(n_weeks, dtype=float)
        natural = config.natural_weekly_change * weeks
        if treated:
            treatment = config.treatment_effect * weeks / (n_weeks - 1)
        else:
            treatment = np.zeros(n_weeks, dtype=float)

        innovation = rng.normal(0.0, config.innovation_sd, size=(n, n_weeks))
        innovation[:, 0] *= 0.25
        noise = np.cumsum(innovation, axis=1)
        engagement = np.clip(baseline[:, None] + natural + treatment + noise, 0.0, 100.0)
        gaze = np.clip(
            0.40 + 0.004 * (engagement - 50.0) + rng.normal(0.0, 0.02, size=engagement.shape),
            0.0,
            1.0,
        )
        vocal = np.clip(
            1.20 + 0.01 * (engagement - 50.0) + rng.normal(0.0, 0.05, size=engagement.shape),
            0.05,
            None,
        )

        start = self._next_id
        self._next_id += n
        patient_ids = [f"{id_prefix}{i:05d}" for i in range(start, start + n)]
        return pd.DataFrame(
            {
                "patient_id": np.repeat(patient_ids, n_weeks),
                "arm": arm,
                "treated": int(treated),
                "week": np.tile(np.arange(n_weeks, dtype=int), n),
                "age": np.repeat(age, n_weeks),
                "baseline_score": np.repeat(baseline, n_weeks),
                "engagement_score": engagement.reshape(-1),
                "gaze_fixation": gaze.reshape(-1),
                "vocal_variability": vocal.reshape(-1),
            }
        )


def build_patient_table(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per patient, with the baseline arm flag and the final-week score."""

    required = ("patient_id", "week", "treated", "engagement_score")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("The trajectory frame is empty.")

    endpoint_week = int(frame["week"].max())
    baseline_week = int(frame["week"].min())
    start = (
        frame.loc[frame["week"] == baseline_week, ["patient_id", "treated"]]
        .drop_duplicates("patient_id")
    )
    end = (
        frame.loc[frame["week"] == endpoint_week, ["patient_id", "engagement_score"]]
        .drop_duplicates("patient_id")
        .rename(columns={"engagement_score": "endpoint_score"})
    )
    table = start.merge(end, on="patient_id", how="inner")
    if table.empty:
        raise ValueError("No patient has both a baseline row and a final-week row.")
    return table.reset_index(drop=True)
