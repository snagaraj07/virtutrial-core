"""Trajectory table contract for files a researcher already has.

The loader checks shape and types, then runs the privacy gate. Extra
columns are kept through validation so a name or note column is refused
instead of being dropped quietly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from privacy import assert_study_table
from simulator import COLUMNS

REQUIRED_COLUMNS = (
    "patient_id",
    "week",
    "treated",
    "age",
    "baseline_score",
    "engagement_score",
    "gaze_fixation",
    "vocal_variability",
)

_ALLOWED_SUFFIXES = {".csv", ".parquet"}


class TrajectorySchemaError(ValueError):
    """The table cannot be analyzed because it breaks the trajectory contract."""


def validate_trajectories(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy that includes the required columns, sorted by patient and week."""

    if not isinstance(frame, pd.DataFrame):
        raise TrajectorySchemaError("Input must be a table.")
    if frame.empty:
        raise TrajectorySchemaError("The table has no rows.")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise TrajectorySchemaError(f"Missing required column: {', '.join(missing)}.")

    out = frame.copy()
    if out["patient_id"].isna().any():
        raise TrajectorySchemaError("Column patient_id must be present on every row.")

    for column in ("week", "treated"):
        converted = pd.to_numeric(out[column], errors="coerce")
        if converted.isna().any():
            raise TrajectorySchemaError(f"Column {column} must be numeric.")
        whole = converted.eq(converted.round())
        out[column] = converted.astype(int) if bool(whole.all()) else converted

    if out.duplicated(subset=["patient_id", "week"]).any():
        raise TrajectorySchemaError("Duplicate patient_id and week rows.")

    treated_per_patient = out.groupby("patient_id", sort=False)["treated"].nunique(dropna=False)
    if bool((treated_per_patient > 1).any()):
        raise TrajectorySchemaError("Column treated must stay constant for each patient.")

    patients = set(out["patient_id"])
    has_baseline = set(out.loc[out["week"] == 0, "patient_id"])
    if patients - has_baseline:
        raise TrajectorySchemaError("Each patient needs a week 0 row.")

    ordered = [column for column in COLUMNS if column in out.columns]
    ordered.extend(column for column in out.columns if column not in ordered)
    return out.loc[:, ordered].sort_values(["patient_id", "week"]).reset_index(drop=True)


def read_trajectories(path: Path) -> pd.DataFrame:
    """Load a CSV or parquet file and validate it."""

    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise TrajectorySchemaError("File suffix must be .csv or .parquet.")
    if suffix == ".csv":
        frame = pd.read_csv(file_path)
    else:
        frame = pd.read_parquet(file_path)
    table = validate_trajectories(frame)
    assert_study_table(table)
    return table
