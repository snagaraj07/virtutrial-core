"""Tests for the external trajectory contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from forecaster import DigitalTwinForecaster
from schema import TrajectorySchemaError, read_trajectories, validate_trajectories
from simulator import TrialSimulator

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic_trajectories.csv"


def test_committed_fixture_is_four_synthetic_rows():
    frame = read_trajectories(FIXTURE)

    assert len(frame) == 4
    assert set(frame["patient_id"]) == {"SYN-001", "SYN-002"}
    assert frame["patient_id"].str.startswith("SYN-").all()
    assert list(frame["week"]) == [0, 1, 0, 1]


def test_simulator_csv_and_parquet_round_trip(tmp_path: Path):
    source = TrialSimulator(seed=3).historical_controls(12)
    csv_path = tmp_path / "history.csv"
    parquet_path = tmp_path / "history.parquet"
    source.to_csv(csv_path, index=False)
    source.to_parquet(parquet_path, index=False)

    from_csv = read_trajectories(csv_path)
    from_parquet = read_trajectories(parquet_path)

    assert len(from_csv) == len(source)
    pd.testing.assert_frame_equal(
        from_csv.reset_index(drop=True),
        from_parquet.reset_index(drop=True),
        check_dtype=False,
    )
    DigitalTwinForecaster().fit(from_csv)


def test_missing_column_names_the_column_only():
    frame = pd.DataFrame({"patient_id": ["SYN-001"], "week": [0]})

    with pytest.raises(TrajectorySchemaError) as caught:
        validate_trajectories(frame)

    message = str(caught.value)
    assert "baseline_score" in message
    assert "SYN-001" not in message


def test_duplicate_patient_week_is_rejected():
    frame = pd.DataFrame(
        {
            "patient_id": ["SYN-001", "SYN-001"],
            "week": [0, 0],
            "treated": [0, 0],
            "age": [8, 8],
            "baseline_score": [50, 50],
            "engagement_score": [50, 51],
            "gaze_fixation": [0.4, 0.4],
            "vocal_variability": [1.2, 1.2],
        }
    )

    with pytest.raises(TrajectorySchemaError, match="Duplicate patient_id and week"):
        validate_trajectories(frame)


def test_non_numeric_week_does_not_echo_the_cell(tmp_path: Path):
    planted = "WEEK-TOKEN-SHOULD-NOT-LEAK"
    file_path = tmp_path / "bad.csv"
    file_path.write_text(
        "patient_id,week,treated,age,baseline_score,engagement_score,gaze_fixation,vocal_variability\n"
        f"SYN-001,{planted},0,8,50,50,0.4,1.2\n"
        "SYN-001,1,0,8,50,51,0.4,1.2\n",
        encoding="utf-8",
    )

    with pytest.raises(TrajectorySchemaError) as caught:
        read_trajectories(file_path)

    message = str(caught.value)
    assert message == "Column week must be numeric."
    assert planted not in message


def test_missing_final_week_is_a_dropout_not_a_schema_error():
    frame = pd.DataFrame(
        {
            "patient_id": ["SYN-001", "SYN-001", "SYN-002"],
            "week": [0, 1, 0],
            "treated": [0, 0, 1],
            "age": [8, 8, 9],
            "baseline_score": [50, 50, 60],
            "engagement_score": [50, 51, 60],
            "gaze_fixation": [0.4, 0.4, 0.45],
            "vocal_variability": [1.2, 1.2, 1.3],
        }
    )

    out = validate_trajectories(frame)

    assert set(out["patient_id"]) == {"SYN-001", "SYN-002"}
    assert 1 not in set(out.loc[out["patient_id"] == "SYN-002", "week"])


def test_other_suffix_is_rejected(tmp_path: Path):
    file_path = tmp_path / "notes.xlsx"
    file_path.write_text("not a table", encoding="utf-8")

    with pytest.raises(TrajectorySchemaError, match=".csv or .parquet"):
        read_trajectories(file_path)
