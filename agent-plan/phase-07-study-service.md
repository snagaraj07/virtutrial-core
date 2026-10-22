# Phase 7 — Study service and audit

```yaml
id: "07"
status: blocked
depends_on: ["06"]
```

## Goal

The same workbench can run in `local` mode or `hosted` mode. Hosted mode refuses to start without identity settings. Every run, export, and delete appends an audit record.

## In scope

Mode switch, OIDC settings loaded from the environment, a study metadata store, and an append-only audit log. Local mode keeps the phase 6 behavior with no login screen.

## Out of scope

Terraform, a production database migration framework beyond the SQL the store needs, and a real identity-provider tenant. Tests use a fake token verifier.

## Security

S3, S4, S5, S8, S9. Hosted mode fails closed: missing `VIRTUTRIAL_OIDC_ISSUER`, `VIRTUTRIAL_OIDC_CLIENT_ID`, or `VIRTUTRIAL_OIDC_CLIENT_SECRET` raises before the app serves. The client secret is read from the environment inside the process and is never written to `report.json` or the audit log. Audit lines are JSON objects appended to a file. The store exposes `append` and `list`, not `update` or `delete` for audit records.

## Deliverables

| Path | Purpose |
| --- | --- |
| `src/audit.py` | Append-only JSONL audit log |
| `src/studies.py` | `StudyStore` protocol and a local JSON or SQLite implementation |
| `src/auth.py` | Settings loader and a verifier interface |
| `src/workbench.py` | Mode switch and protected routes when hosted |
| `tests/test_auth.py` | Fail-closed settings and audit append |
| `README.md` | Document `VIRTUTRIAL_MODE=local` and `hosted` |

## Steps

1. `VIRTUTRIAL_MODE` defaults to `local`.
2. Local mode: routes from phase 6 stay open on `127.0.0.1`. Still record audit events with actor `local-operator`.
3. Hosted mode: `load_hosted_settings()` raises `RuntimeError` listing the missing variable names, not their values.
4. Add a `TokenVerifier` protocol with `verify(token) -> Actor` where `Actor` has `subject` and `role` in `analyst`, `admin`, `auditor`. Tests use a fake verifier.
5. Hosted routes that read or write a study require a verified actor. Auditor can `GET` results and audit. Analyst can upload and run. Admin can also delete a study.
6. `StudyStore.delete` removes the run directory under the data dir and appends an audit event `study.deleted`. It does not remove audit lines.
7. Audit record keys: `ts` (UTC ISO-8601), `actor`, `action`, `study_id`, `run_id`. Actions: `run.created`, `run.executed`, `report.exported`, `predictions.exported`, `study.deleted`.
8. `predictions.exported` is allowed for analyst and admin. Auditor receives 403 on that route.

## Interfaces

```python
def load_hosted_settings(env: Mapping[str, str]) -> HostedSettings:
    """Raise RuntimeError when a required OIDC variable is missing."""

def append_event(path: Path, event: dict) -> None:
    """Append one JSON object and a newline. Do not rewrite the file."""
```

## Tests

- Empty environment and `VIRTUTRIAL_MODE=hosted` fails before routes serve.
- A secret value placed in the environment does not appear in the audit file or in an error string.
- Two appends produce two lines; there is no API that removes the first line.
- Auditor token gets 403 on the predictions route.

## Acceptance

```bash
ruff check .
pytest tests/test_auth.py tests/test_workbench.py
pytest
```

## Done when

Acceptance passes and phase 07 is `complete`. Set phase 08 to `ready`.

## Do not

Do not commit a `.env`. Do not add a default client secret. Do not truncate the audit file on startup. Do not claim the hosted mode is certified for any regulation.
