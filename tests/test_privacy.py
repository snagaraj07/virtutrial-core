"""Tests for identifier refusal."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from privacy import _ALLOWED_COLUMNS, PrivacyError, assert_study_table
from schema import REQUIRED_COLUMNS, read_trajectories


def test_allowed_columns_cover_the_contract():
    assert set(REQUIRED_COLUMNS) <= _ALLOWED_COLUMNS


def test_identifier_column_is_refused():
    frame = pd.DataFrame({"patient_name": ["SYN-001"]})

    with pytest.raises(PrivacyError) as caught:
        assert_study_table(frame)

    assert caught.value.rule_id == "identifier_column"
    assert "patient_name" in str(caught.value)
    assert "SYN-001" not in str(caught.value)


def test_email_value_is_refused_without_echoing_it():
    planted = "person@example.com"
    frame = pd.DataFrame({"contact": [planted]})

    with pytest.raises(PrivacyError) as caught:
        assert_study_table(frame)

    assert caught.value.rule_id == "email_pattern"
    assert planted not in str(caught.value)


def test_ssn_pattern_is_refused_without_echoing_it():
    planted = "123-45-6789"
    frame = pd.DataFrame({"contact": [f"id {planted}"]})

    with pytest.raises(PrivacyError) as caught:
        assert_study_table(frame)

    assert caught.value.rule_id == "ssn_pattern"
    assert planted not in str(caught.value)


def test_loader_refuses_a_name_column(tmp_path: Path):
    file_path = tmp_path / "named.csv"
    file_path.write_text(
        "patient_id,week,treated,age,baseline_score,engagement_score,"
        "gaze_fixation,vocal_variability,patient_name\n"
        "SYN-001,0,0,8,50,50,0.4,1.2,Example Person\n"
        "SYN-001,1,0,8,50,51,0.4,1.2,Example Person\n",
        encoding="utf-8",
    )

    with pytest.raises(PrivacyError) as caught:
        read_trajectories(file_path)

    assert caught.value.rule_id == "identifier_column"
    assert "Example Person" not in str(caught.value)
