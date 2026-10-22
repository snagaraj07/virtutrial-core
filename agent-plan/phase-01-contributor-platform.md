# Phase 1 — Contributor platform

```yaml
id: "01"
status: complete
depends_on: []
```

## Goal

A new contributor can install the library, run the checks, open an issue, and send a pull request. Security reports have a private path.

## In scope

Contributor guide, conduct file, security policy, issue forms, pull request template, Ruff, and a read-only CI workflow.

## Out of scope

Loaders, UI, cloud resources, and any change to the estimand.

## Security

S3 and S7. The workflow permission is `contents: read`. Issue forms require a checkbox that the report has no study data or secrets.

## Deliverables

| Path | Purpose |
| --- | --- |
| `CONTRIBUTING.md` | Setup, where changes go, pull request rules |
| `CODE_OF_CONDUCT.md` | Participation rules and private reporting |
| `SECURITY.md` | Vulnerability reports and supported versions |
| `.github/workflows/ci.yml` | Ruff and pytest on Python 3.9 and 3.12 |
| `.github/ISSUE_TEMPLATE/config.yml` | Disable blank issues; link the advisory form |
| `.github/ISSUE_TEMPLATE/bug.yml` | Bug form |
| `.github/ISSUE_TEMPLATE/feature.yml` | Change-request form |
| `.github/pull_request_template.md` | Test and safety checklist |
| `ruff.toml` | Lint settings for Python 3.9 |
| `setup.py` | Dev extra includes `ruff` |
| `README.md` | Links to the contributor docs and this plan |
| `AGENTS.md` | Entry point for build agents |
| `.gitignore` | Ignores data directories and Terraform state |

## Steps

This phase is already implemented on `main`. The next agent starts at phase 2.

## Interfaces

None.

## Tests

Existing `pytest` suite. CI also runs `ruff check .`.

## Acceptance

```bash
test -f CONTRIBUTING.md
test -f CODE_OF_CONDUCT.md
test -f SECURITY.md
test -f .github/workflows/ci.yml
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Done when

Those commands pass and `manifest.json` shows phase 01 as `complete`.

## Do not

Do not grant the workflow `contents: write`. Do not add a deploy job.
