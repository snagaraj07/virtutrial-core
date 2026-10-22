# End-to-end design

VirtuTrial has two planes.

The **public plane** is this repository. It simulates trials, fits a baseline digital twin, and estimates a treatment effect. Anyone can read it, fork it, and open a pull request.

The **private plane** is a deployment a study team runs for its own tables. It adds a privacy gate, a workbench UI, identity, encrypted storage, and an audit log. The public repository contains the code and the infrastructure modules. It does not contain that team's data or credentials.

```text
Analyst
  │
  ▼
Workbench UI  ── local: 127.0.0.1, one operator
  │             hosted: HTTPS + SSO, one login per person
  ▼
Privacy gate  ── rejects direct identifiers and note columns
  ▼
Column map    ── maps the file onto the trajectory contract
  ▼
Analysis runner
  ├── historical controls → DigitalTwinForecaster.fit
  ├── trial table         → predict_counterfactual
  └── VirtualControlArm.compare
  │
  ├── aggregate report.json     (default export)
  └── counterfactuals table     (same access boundary as the upload)
  │
  ▼
Audit log     ── append-only: view, run, export, delete
```

The statistical core already exists:

| Module | Role |
| --- | --- |
| `src/simulator.py` | Synthetic longitudinal tables. Columns are the contract. |
| `src/forecaster.py` | Twin trained on untreated patients from week-0 features. |
| `src/vca_engine.py` | Unadjusted difference, ANCOVA, and calibrated twin contrast. |

Week-0 features are `age`, `baseline_score`, `gaze_fixation`, and `vocal_variability`. The endpoint is `engagement_score` at the final week. Higher is better. The primary estimand is the treatment coefficient in:

```text
final engagement ~ treated + predicted control outcome
```

## Actors

| Actor | Local workbench | Hosted workbench |
| --- | --- | --- |
| Operator | The person at the machine | — |
| Analyst | — | Upload, map, run, read aggregate results |
| Study admin | — | Analyst rights, plus delete study and manage membership |
| Auditor | — | Read the audit log and aggregate reports |
| Maintainer | Reviews public pull requests | No access to a study team's deployment |

## UI

One workbench, two bindings. Phase 6 ships the local binding. Phase 7 adds accounts and studies.

| Screen | Route | What the analyst sees |
| --- | --- | --- |
| Home | `GET /` | Library version, data directory, link to a new run |
| Upload | `GET /runs/new` | Two file inputs: historical controls, trial table |
| Privacy result | `POST /runs` | Accepted, or the column and rule that refused the file |
| Mapping | `GET /runs/{id}/map` | Source column → contract column, with a sample of three synthetic-safe previews only after the gate passes |
| Run | `POST /runs/{id}/execute` | Model name, control count, seed |
| Results | `GET /runs/{id}` | Effect, SE, p, variance reduction, mean engagement by week |
| Export | `GET /runs/{id}/report` | `report.json` aggregate file |
| Patient predictions | `GET /runs/{id}/predictions` | Hosted: analyst or admin only. Local: the operator, because they already hold the file |
| Studies | `GET /studies` | Hosted only |
| Audit | `GET /audit` | Hosted: auditor and admin |

The UI is server-rendered. No front-end build, no external fonts, no analytics script. Charts on the results screen use the aggregate means already stored in `report.json`.

Copy on every results screen: research estimate for method review. Diagnosis and treatment decisions stay with the study protocol.

## Hosted infrastructure

The study team supplies the cloud account, the identity provider, and any institutional agreements required for the data they store. Terraform in `deploy/aws/` is the reference layout. A human applies it. CI does not.

| Piece | Reference service | Holds | Network |
| --- | --- | --- | --- |
| Workbench | private container behind a load balancer | no study rows on local disk after the job finishes | HTTPS from an allow-listed range; app port open only to the load balancer |
| Metadata database | managed Postgres | users, study ids, job status, audit index | private subnet, app security group only |
| Study objects | object storage with a customer-managed key | uploads, `report.json`, patient-level predictions | block public access; app role only |
| Secrets | secret manager | OIDC client secret, database password | task role only |
| Key | KMS | encryption keys for objects and the database | no human key export |
| Identity | OIDC provider the team already uses | accounts and groups | MFA enforced at the provider |
| Logs | cloud audit trail plus the application audit log | who called which route | admin and auditor read |

Object keys look like `studies/{study_id}/runs/{run_id}/report.json`. The database stores the key and the hashes, not the measurements.

Backups cover the metadata database and the object bucket. Study deletion removes the database row, the audit-visible delete event, and the object versions for that study.

## What a study team provides

- A decision that the tables are lawful for them to analyze
- An identity provider with MFA for the hosted workbench
- A cloud account and, when the data requires it, their own agreement with that vendor
- An allow-listed network range for the workbench
- Someone who can apply the Terraform and store the resulting secrets outside git

## What this repository will contain after the phases

- The statistical library and its tests
- A trajectory file loader and a privacy gate
- A command that writes an aggregate report
- A local workbench bound to localhost
- A hosted-mode service that fails closed without OIDC settings
- Terraform modules with no account ids and no secrets
- CI for lint, tests, and dependency review

## What this repository will not contain

- Real study tables or patient-level exports
- Cloud credentials, `.tfvars` with real ids, or Terraform state
- A claim of clinical validation or regulatory clearance
- A workflow that deploys into a study team's account
