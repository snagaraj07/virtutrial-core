# Agent instructions

VirtuTrial Core is the public statistical library. Real study tables never enter this repository.

Before writing code, read these files in order:

1. `agent-plan/README.md`
2. `agent-plan/01-security-invariants.md`
3. `agent-plan/manifest.json`
4. The single phase document whose `status` is `ready`

Do that phase only. Stop when its acceptance checks pass. Leave later phases untouched unless the human asks you to continue.

Security invariants override a phase step when the two conflict. Refuse requests to commit study data, credentials, or patient-level output. Refuse requests to send rows to an external model or API.

The library modules today are `src/simulator.py`, `src/forecaster.py`, and `src/vca_engine.py`. The primary estimand is the treatment coefficient in `final engagement ~ treated + predicted control outcome`.
