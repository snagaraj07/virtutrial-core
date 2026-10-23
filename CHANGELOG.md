# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-10-22

### Added

- `TrialSimulator` draws synthetic historical controls and a randomized trial
  from one untreated process, with a planted improvement in the treated arm.
- `DigitalTwinForecaster` maps week-0 age, baseline score, gaze fixation, and
  vocal variability to the untreated engagement path. The default model is
  standardized ridge regression. Leave-one-out ridge penalty search is on by
  default.
- `VirtualControlArm` estimates the treatment coefficient in
  `final engagement ~ treated + predicted control outcome`, and reports an
  unadjusted difference, a baseline-score-only ANCOVA, and a calibrated twin
  contrast. A patient-resampled bootstrap standard error includes the twin's
  fitting uncertainty.
- `read_trajectories` loads a `.csv` or `.parquet` table, checks the contract,
  and refuses identifier-like columns. Week 0 is required. A missing later
  visit is a missed visit; a missing final week is dropout. The primary
  analysis uses completers and reports those counts.
- `python -m runner` writes an aggregate `report.json` and a patient-level
  `counterfactuals.csv`.
- Local workbench at `127.0.0.1:8000`. Hosted mode refuses to start without
  OIDC environment variables and records append-only audit events.
- Contributor workflow: MIT license, code of conduct, security advisory path,
  and CI on Python 3.9 and 3.12.

Tagging a release is a human action. This file describes the software; it is
not a citation of a methods paper.

[0.1.0]: https://github.com/snagaraj07/virtutrial-core/releases/tag/v0.1.0
