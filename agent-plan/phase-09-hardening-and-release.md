# Phase 9 — Hardening and release

```yaml
id: "09"
status: blocked
depends_on: ["03", "08"]
```

## Goal

A maintainer can cut a version with a changelog, a dependency review, and a file list that excludes study data and secrets.

## In scope

Dependency-update config, a CI dependency audit that does not fail the build on a network-restricted sandbox without a documented reason, a release checklist, and a note in `CHANGELOG.md` for the workbench and the deployment modules.

## Out of scope

Pushing a tag, publishing to PyPI, and deploying infrastructure. Tagging remains a human action.

## Security

S1, S3, and S7. The audit job uses read-only permissions. It must not receive a cloud credential. The release checklist repeats the gitignore rules.

## Deliverables

| Path | Purpose |
| --- | --- |
| `.github/dependabot.yml` | Weekly updates for pip and GitHub Actions |
| `.github/workflows/ci.yml` | Dependency audit job, read-only |
| `RELEASE.md` | Human checklist for a version tag |
| `CHANGELOG.md` | Unreleased section describing phases 02 through 08 |

## Steps

1. Add Dependabot for `pip` at the repository root and for `github-actions` in `.github/workflows`, weekly.
2. Add a CI job `audit` that installs `pip-audit` and runs it against the environment created by `pip install -e ".[workbench]"`. Permissions remain `contents: read`.
3. Write `RELEASE.md` with this checklist:
   - version bumped in one place and matched in `CITATION.cff` and `CHANGELOG.md`
   - `ruff check .` and `pytest` pass
   - `git status` shows no `.env`, `tfvars`, `tfstate`, or files under `.local-data/`
   - the human, not CI, creates the tag
4. Move the implemented work into the changelog under `Unreleased`. Do not invent a version number beyond `0.1.0` unless the human asks for a bump.
5. README links to `RELEASE.md`.

## Interfaces

No new statistical functions.

## Tests

```bash
ruff check .
pytest
test -f RELEASE.md
test -f .github/dependabot.yml
grep -q pip-audit .github/workflows/ci.yml
git status --porcelain --untracked-files=all | grep -E '\.env$|tfstate|tfvars$' && exit 1 || exit 0
```

Run `pip-audit` when the network allows it. If it cannot reach the advisory database, record that in the summary and keep the job in CI for the hosted runner.

## Done when

Acceptance passes and phase 09 is `complete`. `current_phase` in `manifest.json` becomes `none`.

## Do not

Do not push a tag. Do not publish the package. Do not add production credentials to the audit job. Do not mark the project as clinically validated in the changelog.
