# Phase 6 — Local workbench

```yaml
id: "06"
status: blocked
depends_on: ["04", "05"]
```

## Goal

An operator on one machine can upload two files, see a refusal or a mapping screen, run the analysis, and view the aggregate result in a browser on localhost.

## In scope

A FastAPI application, server-rendered pages, and tests with `TestClient`. Dependencies `fastapi` and `httpx` go in the `dev` extra or a new `workbench` extra. Prefer a `workbench` extra so the library install stays small: `pip install -e ".[workbench]"`.

## Out of scope

Accounts, SSO, Postgres, and any bind address other than `127.0.0.1`.

## Security

S1, S2, S4, S5, S6, S10. The server factory refuses a host other than `127.0.0.1`. Uploads land in `VIRTUTRIAL_DATA_DIR` (default `.local-data`), which is gitignored. The results page reads `report.json` only. The predictions route exists and returns the CSV only to the local operator. No template loads a remote script, font, or image.

## Deliverables

| Path | Purpose |
| --- | --- |
| `src/workbench.py` | App factory and routes |
| `src/templates/*.html` | Server-rendered screens |
| `tests/test_workbench.py` | Client tests against temporary data dirs |
| `README.md` | How to start the local workbench |

## Steps

1. `create_app(data_dir: Path) -> FastAPI`. `main()` reads `VIRTUTRIAL_DATA_DIR` and calls `uvicorn` only if you add that server, bound to `127.0.0.1` and port `8000`. Provide `python -m workbench`.
2. If `create_app` is asked to prepare a public bind, raise `RuntimeError` before serving. Encode the allowed host as the string `127.0.0.1` in `main`.
3. Routes from `00-system-design.md`: `GET /`, `GET /runs/new`, `POST /runs`, `GET /runs/{id}/map`, `POST /runs/{id}/execute`, `GET /runs/{id}`, `GET /runs/{id}/report`, `GET /runs/{id}/predictions`.
4. `POST /runs` streams each file to `data_dir/runs/{id}/` and runs `read_trajectories`. On `PrivacyError` or `TrajectorySchemaError`, render the rule id and column. Do not render cell text.
5. Mapping screen: when the contract names already match, show them as confirmed and allow execute. Custom renaming can wait; auto-match of `REQUIRED_COLUMNS` is enough for this phase.
6. Execute calls `run_study` and redirects to the results page.
7. Results page shows ancova effect, SE, p, and the research-estimate sentence from the design doc.
8. Limit each upload to 50 MB. Reject a path that escapes `data_dir`.

## Interfaces

```python
def create_app(data_dir: Path) -> FastAPI:
    """Local workbench. Files stay under data_dir."""
```

Run ids are random URL-safe tokens, not the original filename.

## Tests

Use FastAPI `TestClient` and `tmp_path`.

- A simulator CSV pair reaches the results page and shows a numeric ancova effect.
- A column named `patient_name` renders `PrivacyError` and does not create `report.json`.
- `GET /runs/{id}/report` body has no `patient_id` key.
- A run id containing `../` returns 404.

## Acceptance

```bash
python -m pip install -e ".[workbench]"
ruff check .
pytest tests/test_workbench.py
pytest
```

## Done when

Acceptance passes and phase 06 is `complete`. Set phase 07 to `ready`.

## Do not

Do not add a user table. Do not call a CDN. Do not log uploaded bytes. Do not bind `0.0.0.0`.
