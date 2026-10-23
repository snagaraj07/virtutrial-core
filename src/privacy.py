"""Refusal checks for obvious direct identifiers.

The gate blocks identifier-like column names and two value patterns: an
email address, and a ###-##-#### digit pattern. It does not make a file
lawful to analyze, and it does not redact text inside an allowed column.
Free-text columns are refused by name before their contents are kept.
"""

from __future__ import annotations

import re

import pandas as pd

_ALLOWED_COLUMNS = {
    "patient_id",
    "week",
    "treated",
    "age",
    "baseline_score",
    "engagement_score",
    "gaze_fixation",
    "vocal_variability",
    "arm",
}
_BLOCKED_TOKENS = (
    "firstname",
    "lastname",
    "freetext",
    "narrative",
    "address",
    "comment",
    "birth",
    "email",
    "phone",
    "name",
    "note",
    "ssn",
    "mrn",
    "dob",
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"\d{3}-\d{2}-\d{4}")


class PrivacyError(ValueError):
    """The table was refused before a model was fit."""

    def __init__(self, message: str, rule_id: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id


def assert_study_table(frame: pd.DataFrame) -> None:
    """Raise PrivacyError when the table fails a refusal rule."""

    for column in frame.columns:
        if column in _ALLOWED_COLUMNS:
            continue
        normalized = "".join(character for character in str(column).lower() if character.isalnum())
        if any(token in normalized for token in _BLOCKED_TOKENS):
            raise PrivacyError(
                f"Column {column} was refused.",
                "identifier_column",
            )

    for column in frame.columns:
        series = frame[column]
        if not (series.dtype == object or pd.api.types.is_string_dtype(series)):
            continue
        for value in series.dropna():
            text = str(value)
            if _EMAIL.search(text):
                raise PrivacyError(
                    f"Column {column} was refused.",
                    "email_pattern",
                )
            if _SSN.search(text):
                raise PrivacyError(
                    f"Column {column} was refused.",
                    "ssn_pattern",
                )
