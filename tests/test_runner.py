"""Tests for the aggregate study report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runner import REPORT_KEYS, run_study
from simulator import TrialSimulator


def _write_pair(tmp_path: Path) -> tuple[Path, Path, int]:
    simulator = TrialSimulator(seed=4)
    history = simulator.historical_controls(30)
    trial = simulator.trial(n_treatment=20, n_control=16)
    history_path = tmp_path / "history.csv"
    trial_path = tmp_path / "trial.csv"
    history.to_csv(history_path, index=False)
    trial.to_csv(trial_path, index=False)
    return history_path, trial_path, trial["patient_id"].nunique()


def test_report_is_aggregate_and_predictions_are_one_row_per_patient(tmp_path: Path):
    history_path, trial_path, n_patients = _write_pair(tmp_path)
    output = tmp_path / "out"

    report = run_study(history_path, trial_path, output, n_boot=8)

    assert tuple(report) == REPORT_KEYS
    assert report["planted_effect"] is None
    assert report["schema_version"] == 3
    assert report["n_boot"] == 8
    assert report["n_boot_ok"] >= 2
    assert report["follow_up"]["n_dropouts"] == 0
    assert report["follow_up"]["endpoint"]["kind"] == "synthetic"
    assert report["manifest"]["ridge_tuned"] is True
    text = (output / "report.json").read_text(encoding="utf-8")
    assert "patient_id" not in text
    assert json.loads(text)["n_treatment"] == report["n_treatment"]
    assert isinstance(report["baseline_ancova_se"], float)
    assert report["twin_check"]["n_controls"] == report["n_control"]
    assert [row["feature"] for row in report["baseline_comparison"]] == [
        "age",
        "baseline_score",
        "gaze_fixation",
        "vocal_variability",
    ]
    assert report["manifest"]["history_file"]["sha256"] == (
        hashlib.sha256(history_path.read_bytes()).hexdigest()
    )
    assert report["manifest"]["n_training_controls"] == report["n_history_controls"]
    predictions = (output / "counterfactuals.csv").read_text(encoding="utf-8").strip().splitlines()
    assert predictions[0] == "patient_id,counterfactual"
    assert len(predictions) - 1 == n_patients
