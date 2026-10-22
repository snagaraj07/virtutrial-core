# Security invariants

These rules apply to every phase. If a phase step conflicts with an invariant, follow the invariant and record the conflict in the phase summary.

| ID | Rule |
| --- | --- |
| S1 | Git contains source, docs, tests, and synthetic fixtures only. Study tables, patient-level predictions, and exports stay in `VIRTUTRIAL_DATA_DIR`. |
| S2 | Row-level values are never sent to an external API, including hosted language models, analytics, and error trackers. |
| S3 | Secrets come from the environment or a secret manager. Source has no default passwords, tokens, access keys, or connection strings with credentials. |
| S4 | The local workbench listens on `127.0.0.1` only. A hosted service requires authentication on every study route. |
| S5 | Patient-level predictions use the same access boundary as the source table. The default download is the aggregate report. |
| S6 | Direct-identifier columns and free-text note columns are rejected before a model fits. The privacy gate is a refusal check, not a full de-identification product. |
| S7 | CI tokens are read-only. Workflows do not deploy and do not receive production credentials. |
| S8 | Deleting a study removes its metadata, objects, and patient-level outputs. |
| S9 | Access, run, export, and delete events append to an audit log. The application does not update or delete past audit lines. |
| S10 | Screens and reports describe research estimates. They do not diagnose, recommend a treatment, or claim a regulatory clearance. |

## Data classes

| Class | Examples | Allowed in git | Allowed on screen by default |
| --- | --- | --- | --- |
| Synthetic fixture | `TrialSimulator` output, `tests/fixtures` with ids `SYN-` | Yes | Yes |
| Aggregate result | effect, SE, p, mean curve, library version | Yes, if produced from a fixture in a test | Yes |
| Patient-level | uploaded rows, counterfactual per `patient_id` | No | Only behind the same permission as the source table |
| Secret | OIDC client secret, database password, KMS key material | No | No |
| Metadata | study name, row count, schema version, actor, timestamp | Yes, as an empty schema or a synthetic test record | Yes |

## Agent refusals

Stop and tell the human when a request asks you to:

- commit or paste a real study file, a credential, or a patient-level export
- bind the workbench to `0.0.0.0` or disable authentication on a hosted route
- log row values, including inside exception messages and test output that is committed
- call a third-party API with table contents
- mark the software as clinically validated, HIPAA-certified, or cleared for treatment decisions

A deploying organization that stores protected health information also needs its own agreements with the cloud vendor, its identity provider, and its institution. Those agreements are outside this repository.
