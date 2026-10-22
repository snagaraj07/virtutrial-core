"""Virtual control arm comparison and a small-sample power check.

The primary estimand is the treatment coefficient in

    endpoint ~ intercept + treated + digital_twin_counterfactual

The counterfactual is the final-week outcome the twin expects under control.
Randomization keeps that baseline prediction from biasing the treatment
coefficient. Concurrent controls stay in the model so the trial still has an
observed anchor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from forecaster import DigitalTwinForecaster
from simulator import SimulatorConfig, TrialSimulator, build_patient_table


@dataclass
class VCAResult:
    """Estimates from one trial analysis."""

    n_treatment: int
    n_control: int
    ancova_effect: float
    ancova_se: float
    ancova_p: float
    counterfactual_effect: float
    counterfactual_se: float
    counterfactual_p: float
    unadjusted_effect: float
    unadjusted_se: float
    unadjusted_p: float
    outcome_sd: float
    residual_sd: float
    variance_reduction: float

    def summary(self) -> str:
        return "\n".join(
            [
                f"Treatment patients: {self.n_treatment}",
                f"Concurrent controls: {self.n_control}",
                (
                    f"Unadjusted difference: {self.unadjusted_effect:.2f} "
                    f"(SE {self.unadjusted_se:.2f}, p {self.unadjusted_p:.3f})"
                ),
                (
                    f"Virtual control arm (ANCOVA): {self.ancova_effect:.2f} "
                    f"(SE {self.ancova_se:.2f}, p {self.ancova_p:.3f})"
                ),
                (
                    f"Calibrated twin contrast: {self.counterfactual_effect:.2f} "
                    f"(SE {self.counterfactual_se:.2f}, p {self.counterfactual_p:.3f})"
                ),
                f"Outcome SD: {self.outcome_sd:.2f}",
                f"ANCOVA residual SD: {self.residual_sd:.2f}",
                f"Variance reduction: {self.variance_reduction:.1%}",
            ]
        )


@dataclass
class PowerStudyResult:
    """Monte Carlo comparison of a full control arm and a half-size virtual arm."""

    n_sims: int
    n_treatment: int
    n_control_full: int
    n_control_reduced: int
    n_history: int
    alpha: float
    planted_effect: float
    full_unadjusted_power: float
    reduced_unadjusted_power: float
    reduced_vca_power: float
    full_unadjusted_mean_se: float
    reduced_unadjusted_mean_se: float
    reduced_vca_mean_se: float
    mean_variance_reduction: float

    def summary(self) -> str:
        cut = 1.0 - (self.n_control_reduced / self.n_control_full)
        return "\n".join(
            [
                f"Simulations: {self.n_sims}",
                f"Historical controls per simulation: {self.n_history}",
                f"Treatment arm: {self.n_treatment}",
                f"Full concurrent control arm: {self.n_control_full}",
                f"Reduced concurrent control arm: {self.n_control_reduced} ({cut:.0%} fewer)",
                f"Planted treatment effect: {self.planted_effect:.2f} points",
                "",
                f"Empirical power at alpha {self.alpha:.2f}, and mean standard error:",
                (
                    f"  Full control arm, unadjusted:     "
                    f"power {self.full_unadjusted_power:.0%}, "
                    f"mean SE {self.full_unadjusted_mean_se:.2f}"
                ),
                (
                    f"  Reduced control arm, unadjusted:  "
                    f"power {self.reduced_unadjusted_power:.0%}, "
                    f"mean SE {self.reduced_unadjusted_mean_se:.2f}"
                ),
                (
                    f"  Reduced control arm, virtual arm: "
                    f"power {self.reduced_vca_power:.0%}, "
                    f"mean SE {self.reduced_vca_mean_se:.2f}"
                ),
                f"  Mean ANCOVA variance reduction:   {self.mean_variance_reduction:.0%}",
            ]
        )


class VirtualControlArm:
    """Compare an observed treatment arm with a twin-adjusted control arm."""

    def compare(self, trial: pd.DataFrame, counterfactuals: pd.DataFrame) -> VCAResult:
        """Estimate the treatment effect for one simulated or external trial table."""

        patients = build_patient_table(trial)
        predictions = _validated_predictions(counterfactuals)
        merged = patients.merge(predictions, on="patient_id", how="left")
        if merged["counterfactual"].isna().any():
            missing = int(merged["counterfactual"].isna().sum())
            raise ValueError(f"Missing counterfactual predictions for {missing} patients.")

        treated_mask = merged["treated"].to_numpy(dtype=bool)
        n_treatment = int(treated_mask.sum())
        n_control = int((~treated_mask).sum())
        if n_treatment < 2 or n_control < 2:
            raise ValueError("Need at least 2 patients in each arm.")

        outcome = merged["endpoint_score"].to_numpy(dtype=float)
        prognostic = merged["counterfactual"].to_numpy(dtype=float)
        if float(np.std(prognostic)) < 1e-8:
            raise ValueError(
                "Counterfactual scores have no variation, so ANCOVA cannot adjust for them."
            )

        unadjusted = _welch(outcome[treated_mask], outcome[~treated_mask])
        ancova = _ancova(outcome, treated_mask.astype(float), prognostic)
        contrast = _calibrated_contrast(
            outcome[treated_mask],
            prognostic[treated_mask],
            outcome[~treated_mask],
            prognostic[~treated_mask],
        )
        outcome_sd = float(outcome.std(ddof=1))
        if outcome_sd > 0:
            variance_reduction = 1.0 - (ancova.residual_sd ** 2) / (outcome_sd ** 2)
        else:
            variance_reduction = 0.0

        return VCAResult(
            n_treatment=n_treatment,
            n_control=n_control,
            ancova_effect=ancova.estimate,
            ancova_se=ancova.std_error,
            ancova_p=ancova.p_value,
            counterfactual_effect=contrast.estimate,
            counterfactual_se=contrast.std_error,
            counterfactual_p=contrast.p_value,
            unadjusted_effect=unadjusted.estimate,
            unadjusted_se=unadjusted.std_error,
            unadjusted_p=unadjusted.p_value,
            outcome_sd=outcome_sd,
            residual_sd=ancova.residual_sd,
            variance_reduction=float(variance_reduction),
        )


def estimate_power(
    seed: int = 7,
    n_sims: int = 100,
    n_treatment: int = 40,
    n_control: int = 40,
    n_history: int = 400,
    alpha: float = 0.05,
    config: SimulatorConfig | None = None,
) -> PowerStudyResult:
    """Compare a full unadjusted control arm with a half-size virtual control arm.

    Each simulation draws historical controls and a trial from the same
    process, fits the twin on history, then analyzes the full concurrent
    control arm and the first half of those controls. The historical cohort
    is what gives the virtual arm its extra precision.
    """

    if n_sims < 1:
        raise ValueError("n_sims must be at least 1.")
    if n_control < 10:
        raise ValueError("n_control must be at least 10 so the half-size arm still has 5 controls.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")

    config = config or SimulatorConfig()
    full_p: list[float] = []
    reduced_p: list[float] = []
    virtual_p: list[float] = []
    full_se: list[float] = []
    reduced_se: list[float] = []
    virtual_se: list[float] = []
    variance_reduction: list[float] = []
    n_reduced = n_control // 2

    for offset in range(n_sims):
        simulator = TrialSimulator(config=config, seed=seed + offset)
        history = simulator.historical_controls(n_history)
        trial = simulator.trial(n_treatment, n_control)
        counterfactuals = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)
        full = VirtualControlArm().compare(trial, counterfactuals)

        control_ids = (
            trial.loc[trial["treated"] == 0, "patient_id"].drop_duplicates().to_numpy()
        )
        keep_ids = set(control_ids[:n_reduced]) | set(
            trial.loc[trial["treated"] == 1, "patient_id"].drop_duplicates().to_numpy()
        )
        reduced_trial = trial.loc[trial["patient_id"].isin(keep_ids)]
        reduced_predictions = counterfactuals.loc[counterfactuals["patient_id"].isin(keep_ids)]
        reduced = VirtualControlArm().compare(reduced_trial, reduced_predictions)

        full_p.append(full.unadjusted_p)
        reduced_p.append(reduced.unadjusted_p)
        virtual_p.append(reduced.ancova_p)
        full_se.append(full.unadjusted_se)
        reduced_se.append(reduced.unadjusted_se)
        virtual_se.append(reduced.ancova_se)
        variance_reduction.append(reduced.variance_reduction)

    return PowerStudyResult(
        n_sims=n_sims,
        n_treatment=n_treatment,
        n_control_full=n_control,
        n_control_reduced=n_reduced,
        n_history=n_history,
        alpha=alpha,
        planted_effect=config.treatment_effect,
        full_unadjusted_power=_power(full_p, alpha),
        reduced_unadjusted_power=_power(reduced_p, alpha),
        reduced_vca_power=_power(virtual_p, alpha),
        full_unadjusted_mean_se=float(np.mean(full_se)),
        reduced_unadjusted_mean_se=float(np.mean(reduced_se)),
        reduced_vca_mean_se=float(np.mean(virtual_se)),
        mean_variance_reduction=float(np.mean(variance_reduction)),
    )


@dataclass
class _Estimate:
    estimate: float
    std_error: float
    p_value: float
    residual_sd: float = 0.0


def _validated_predictions(counterfactuals: pd.DataFrame) -> pd.DataFrame:
    required = ("patient_id", "counterfactual")
    missing = [column for column in required if column not in counterfactuals.columns]
    if missing:
        raise ValueError(
            "counterfactuals must include patient_id and counterfactual; "
            f"missing {', '.join(missing)}."
        )
    if counterfactuals["patient_id"].duplicated().any():
        raise ValueError("counterfactuals has duplicate patient_id values.")
    return counterfactuals.loc[:, ["patient_id", "counterfactual"]]


def _welch(treatment: np.ndarray, control: np.ndarray) -> _Estimate:
    result = stats.ttest_ind(treatment, control, equal_var=False)
    std_error = float(
        np.sqrt(treatment.var(ddof=1) / len(treatment) + control.var(ddof=1) / len(control))
    )
    return _Estimate(
        estimate=float(treatment.mean() - control.mean()),
        std_error=std_error,
        p_value=float(result.pvalue),
    )


def _ancova(outcome: np.ndarray, treated: np.ndarray, prognostic: np.ndarray) -> _Estimate:
    design = np.column_stack([np.ones(len(outcome)), treated, prognostic])
    coefficient, _, _, _ = np.linalg.lstsq(design, outcome, rcond=None)
    residual = outcome - np.dot(design, coefficient)
    degrees = len(outcome) - design.shape[1]
    if degrees <= 0:
        raise ValueError("Not enough patients for ANCOVA.")
    sigma2 = float(np.sum(residual ** 2) / degrees)
    try:
        covariance = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "ANCOVA design matrix is singular. Prognostic scores need to vary within the trial."
        ) from exc
    std_error = float(np.sqrt(covariance[1, 1] * sigma2))
    estimate = float(coefficient[1])
    if std_error > 0:
        p_value = float(2 * stats.t.sf(abs(estimate / std_error), df=degrees))
    else:
        p_value = 0.0
    return _Estimate(estimate, std_error, p_value, residual_sd=float(np.sqrt(sigma2)))


def _calibrated_contrast(
    treatment_outcome: np.ndarray,
    treatment_prognostic: np.ndarray,
    control_outcome: np.ndarray,
    control_prognostic: np.ndarray,
) -> _Estimate:
    """Recalibrate the twin on concurrent controls, then contrast the treated patients."""

    slope, intercept = np.polyfit(control_prognostic, control_outcome, deg=1)
    deltas = treatment_outcome - (intercept + slope * treatment_prognostic)
    estimate = float(deltas.mean())
    std_error = float(deltas.std(ddof=1) / np.sqrt(len(deltas)))
    degrees = len(deltas) - 1
    if std_error > 0 and degrees > 0:
        p_value = float(2 * stats.t.sf(abs(estimate / std_error), df=degrees))
    else:
        p_value = 1.0
    return _Estimate(estimate, std_error, p_value)


def _power(p_values: list[float], alpha: float) -> float:
    return float(np.mean(np.asarray(p_values) < alpha))
