# Agent build plan

This folder is the build contract for VirtuTrial. An agent reads it in the order below and implements one phase per session.

## Read order

1. `01-security-invariants.md` — rules that override every phase
2. `00-system-design.md` — end-to-end design
3. `manifest.json` — which phase is next
4. The phase file with `"status": "ready"`

`AGENTS.md` at the repository root points here.

## How to run one phase

1. Confirm every id in `depends_on` has `"status": "complete"` in `manifest.json`.
2. Read that phase file from top to bottom. The sections are always in the same order: Goal, In scope, Out of scope, Security, Deliverables, Steps, Interfaces, Tests, Acceptance, Done when, Do not.
3. Create or edit only the paths in Deliverables, plus tests those steps name.
4. Run every command in Acceptance from the repository root. All of them must pass.
5. Set that phase's `status` to `complete` in `manifest.json`, and set the next phase's `status` to `ready`.
6. Stop. Summarize the files changed and the acceptance output. Do not start the next phase unless the human asks.

## Status values

| Status | Meaning |
| --- | --- |
| `complete` | Acceptance checks passed and the files exist |
| `ready` | The next phase an agent may start |
| `blocked` | A dependency is still incomplete |

## Repository split

| Plane | Where it lives | What it may contain |
| --- | --- | --- |
| Public library | this git repository | statistical code, synthetic fixtures, docs, tests |
| Study data | `VIRTUTRIAL_DATA_DIR`, default `.local-data/` | uploaded tables and patient-level predictions |
| Hosted deployment | the study team's cloud account | encrypted objects, metadata database, audit log |

`.local-data/`, `data/`, `studies/`, and `uploads/` are gitignored. An agent must not force-add them.
