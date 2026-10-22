"""Synthetic autism-trial demo for the VirtuTrial virtual control arm.

The scores are simulated. The script shows how a baseline digital twin,
trained on historical controls from the same process, changes the precision
of a treatment comparison when the concurrent control arm is cut in half.

Run from the repository root:

    python examples/autism_trial_demo.py
    python examples/autism_trial_demo.py --sims 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forecaster import DigitalTwinForecaster
from simulator import TrialSimulator
from vca_engine import PowerStudyResult, VirtualControlArm, estimate_power


def run_demo(seed: int = 7, n_sims: int = 100) -> PowerStudyResult:
    """Print one worked trial, then a Monte Carlo power comparison."""

    simulator = TrialSimulator(seed=seed)
    history = simulator.historical_controls(500)
    trial = simulator.trial(n_treatment=80, n_control=40)
    counterfactuals = DigitalTwinForecaster().fit(history).predict_counterfactual(trial)
    comparison = VirtualControlArm().compare(trial, counterfactuals)
    study = estimate_power(seed=seed, n_sims=n_sims)

    print("VirtuTrial synthetic autism-trial demo")
    print("Endpoint: functional engagement score, higher is better.")
    print("The score, gaze stream, and vocal stream are synthetic.")
    print()
    print("One simulated trial (80 treated, 40 concurrent controls)")
    print(f"Historical controls used to train the twin: {history['patient_id'].nunique()}")
    print(comparison.summary())
    print()
    print("Operating characteristics when the concurrent control arm is cut in half")
    print(study.summary())
    print()
    if (
        study.reduced_vca_power + 0.02 >= study.full_unadjusted_power
        and study.reduced_vca_mean_se < study.full_unadjusted_mean_se
    ):
        print(
            "On this synthetic endpoint, the virtual control arm with half the "
            "concurrent controls matched or exceeded the power of an unadjusted "
            "analysis that used the full control arm. The gain comes from the "
            "historical cohort the twin was trained on."
        )
    else:
        print(
            "On this synthetic run, halving the control arm and adjusting with "
            "the twin did not fully recover the full-arm unadjusted power. "
            "Use the standard errors above to see what the twin did recover."
        )
    print("This is a simulation for method development, not evidence about a real trial.")
    return study


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the synthetic VirtuTrial autism-trial demo."
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--sims", type=int, default=100, help="Monte Carlo replications")
    args = parser.parse_args()
    run_demo(seed=args.seed, n_sims=args.sims)


if __name__ == "__main__":
    main()
