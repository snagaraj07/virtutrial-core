# Phase 5 — Privacy gate

```yaml
id: "05"
status: blocked
depends_on: ["02"]
```

## Goal

The loader refuses tables that carry direct identifiers or free-text notes before any model runs.

## In scope

`src/privacy.py`, a call from `read_trajectories` into the gate, and tests that use fake patterns.

## Out of scope

A full de-identification pipeline, natural-language note scrubbing beyond column-name refusal, and the UI. Document the limit in the `privacy.py` module docstring and in the README.

## Security

S2 and S6. Error messages name the column and the rule id. They do not echo the cell value. Tests may include fake tokens such as `SYN-SSN` and `person@example.com` inside `tmp_path` files that are not committed.

## Deliverables

| Path | Purpose |
| --- | --- |
| `src/privacy.py` | Column and value-pattern refusal |
| `src/schema.py` | `read_trajectories` calls the gate after the schema check |
| `tests/test_privacy.py` | Refusal cases |
| `README.md` | State what the gate refuses and what it does not do |

## Steps

1. Add `PrivacyError(ValueError)` with attribute `rule_id: str`.
2. Refuse a column whose normalized name (lowercase, alphanumeric only) contains any of: `name`, `firstname`, `lastname`, `ssn`, `mrn`, `address`, `phone`, `email`, `dob`, `birth`, `note`, `narrative`, `freetext`, `comment`.
3. Allow the contract columns even though `baseline_score` contains no blocked token. Check the blocked list against column names, not against numeric scores.
4. Scan string values for an email pattern and a pattern of three-two-four digits (`###-##-####`). On a match, raise `PrivacyError` with `rule_id` `email_pattern` or `ssn_pattern` and do not include the matched text.
5. Call this from `read_trajectories` after `validate_trajectories`.
6. README paragraph: the gate blocks obvious identifier columns and two value patterns. It does not make a file lawful to use, and it does not remove identifiers hidden inside an allowed column's free text because free-text columns are refused by name.

## Interfaces

```python
class PrivacyError(ValueError):
    rule_id: str

def assert_study_table(frame: pd.DataFrame) -> None:
    """Raise PrivacyError when the table fails a refusal rule."""
```

## Tests

Each test builds a one-column offender in memory. Assert `rule_id`. Assert the exception string does not contain the planted email or the planted digit pattern.

## Acceptance

```bash
ruff check .
pytest tests/test_privacy.py tests/test_schema.py
pytest
```

## Done when

Acceptance passes, phase 05 is `complete`, and phase 06 is `ready` if phase 04 is already `complete`. If phase 04 is still blocked or ready, leave phase 06 blocked.

## Do not

Do not send the frame to an external detector. Do not write rejected rows to a log file. Do not weaken the gate with a skip flag whose default is off-in-name-only; a skip flag is out of scope.
