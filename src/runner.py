"""Run one virtual-control comparison and write an aggregate report.

``report.json`` holds study-level numbers only. Per-patient predictions go
in ``counterfactuals.csv`` beside it and should be treated with the same
care as the source table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from diagnostics import baseline_comparison, follow_up, run_manifest, twin_check
from forecaster import DigitalTwinForecaster
from schema import TrajectorySchemaError, read_trajectories
from vca_engine import VirtualControlArm, bootstrap_ancova

REPORT_KEYS = (
    "schema_version",
    "library_version",
    "n_history_controls",
    "n_treatment",
    "n_control",
    "planted_effect",
    "unadjusted_effect",
    "unadjusted_se",
    "unadjusted_p",
    "baseline_ancova_effect",
    "baseline_ancova_se",
    "baseline_ancova_p",
    "ancova_effect",
    "ancova_se",
    "ancova_p",
    "counterfactual_effect",
    "counterfactual_se",
    "counterfactual_p",
    "outcome_sd",
    "residual_sd",
    "variance_reduction",
    "bootstrap_se",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "n_boot",
    "n_boot_ok",
    "mean_engagement",
    "baseline_comparison",
    "twin_check",
    "follow_up",
    "manifest",
)


def library_version() -> str:
    """Read the version string stored in ``src/__init__.py``."""

    init_file = Path(__file__).with_name("__init__.py")
    for line in init_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("The library version is missing from src/__init__.py.")


def run_study(
    history_path: Path,
    trial_path: Path,
    output_dir: Path,
    n_boot: int = 20,
    tune: bool = True,
    bootstrap_seed: int = 0,
) -> dict:
    """Fit a twin on the history file and compare it with the trial file."""

    history = read_trajectories(history_path)
    trial = read_trajectories(trial_path)
    control_ids = history.loc[history["treated"] == 0, "patient_id"].nunique()
    if int(control_ids) < 10:
        raise TrajectorySchemaError("At least 10 control patients are required.")

    try:
        forecaster = DigitalTwinForecaster(tune=tune).fit(history)
        counterfactuals = forecaster.predict_counterfactual(trial)
        comparison = VirtualControlArm().compare(trial, counterfactuals)
        boot = bootstrap_ancova(
            history, trial, n_boot=n_boot, seed=bootstrap_seed, tune=tune
        )
    except ValueError as exc:
        raise TrajectorySchemaError(str(exc)) from None

    report = {
        "schema_version": 3,
        "library_version": library_version(),
        "n_history_controls": int(control_ids),
        "n_treatment": int(comparison.n_treatment),
        "n_control": int(comparison.n_control),
        "planted_effect": None,
        "unadjusted_effect": float(comparison.unadjusted_effect),
        "unadjusted_se": float(comparison.unadjusted_se),
        "unadjusted_p": float(comparison.unadjusted_p),
        "baseline_ancova_effect": float(comparison.baseline_effect),
        "baseline_ancova_se": float(comparison.baseline_se),
        "baseline_ancova_p": float(comparison.baseline_p),
        "ancova_effect": float(comparison.ancova_effect),
        "ancova_se": float(comparison.ancova_se),
        "ancova_p": float(comparison.ancova_p),
        "counterfactual_effect": float(comparison.counterfactual_effect),
        "counterfactual_se": float(comparison.counterfactual_se),
        "counterfactual_p": float(comparison.counterfactual_p),
        "outcome_sd": float(comparison.outcome_sd),
        "residual_sd": float(comparison.residual_sd),
        "variance_reduction": float(comparison.variance_reduction),
        "bootstrap_se": float(boot["bootstrap_se"]),
        "bootstrap_ci_low": float(boot["bootstrap_ci_low"]),
        "bootstrap_ci_high": float(boot["bootstrap_ci_high"]),
        "n_boot": int(boot["n_boot"]),
        "n_boot_ok": int(boot["n_boot_ok"]),
        "mean_engagement": _mean_engagement(trial),
        "baseline_comparison": baseline_comparison(history, trial),
        "twin_check": twin_check(trial, counterfactuals),
        "follow_up": follow_up(history, trial),
        "manifest": run_manifest(history_path, trial_path, forecaster),
    }
    report["manifest"]["random_seed"] = int(bootstrap_seed)
    if "patient_id" in json.dumps(report):
        raise RuntimeError("The aggregate report included a patient identifier.")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    predictions = counterfactuals.loc[:, ["patient_id", "counterfactual"]].copy()
    predictions.to_csv(output / "counterfactuals.csv", index=False)
    return report


def _mean_engagement(trial: pd.DataFrame) -> list[dict]:
    frame = trial
    if "arm" not in frame.columns:
        frame = frame.copy()
        frame["arm"] = frame["treated"].map({0: "control", 1: "treatment"}).fillna("unknown")
    grouped = (
        frame.groupby(["arm", "week"], as_index=False)["engagement_score"].mean()
    )
    means = []
    for row in grouped.itertuples(index=False):
        means.append(
            {
                "arm": str(row.arm),
                "week": int(row.week),
                "mean": round(float(row.engagement_score), 4),
            }
        )
    return means


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a trial table with a digital twin trained on historical controls."
    )
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--trial", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_study(args.history, args.trial, args.output)
    print(
        f"ANCOVA effect {report['ancova_effect']:.2f} "
        f"(SE {report['ancova_se']:.2f}, p {report['ancova_p']:.3f})"
    )
    print(
        f"Baseline-score ANCOVA {report['baseline_ancova_effect']:.2f} "
        f"(SE {report['baseline_ancova_se']:.2f}, p {report['baseline_ancova_p']:.3f})"
    )
    check = report["twin_check"]
    print(
        f"Twin on {check['n_controls']} concurrent controls: "
        f"RMSE {check['rmse']:.2f}, mean error {check['mean_error']:.2f}"
    )
    print(
        f"Bootstrap SE {report['bootstrap_se']:.2f} "
        f"[{report['bootstrap_ci_low']:.2f}, {report['bootstrap_ci_high']:.2f}] "
        f"from {report['n_boot_ok']} of {report['n_boot']} replicates"
    )
    follow = report["follow_up"]
    print(
        f"Follow-up: {follow['n_completers']} completers, "
        f"{follow['n_dropouts']} dropouts, "
        f"{follow['n_missed_visits']} missed visits"
    )
    print(f"Wrote {args.output / 'report.json'}")


if __name__ == "__main__":
    main()
