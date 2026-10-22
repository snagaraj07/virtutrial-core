# Security policy

VirtuTrial Core is a statistical library. A vulnerability is a flaw that can expose study data, weaken an access boundary, leak a secret, or silently change a treatment estimate.

## Reporting

Open a private advisory:

https://github.com/snagaraj07/virtutrial-core/security/advisories/new

Include the version, the component, and a description that lets a maintainer reproduce the issue on synthetic data.

Do not open a public issue for a vulnerability. Do not attach study tables, patient-level output, access keys, tokens, or screenshots that show them.

## Supported versions

| Version | Security fixes |
| --- | --- |
| 0.1.x on `main` | Yes, while this is the only maintained line |

## Rules for this repository

- Study tables and patient-level outputs stay out of git, issues, and pull requests. `.gitignore` excludes `data/`, `studies/`, `uploads/`, and `.local-data/`.
- Secrets stay in the environment or a secret manager. Source code has no default passwords, tokens, or cloud keys.
- CI uses a read-only `GITHUB_TOKEN`.
- The library does not send rows to an external API.

The deployment design and the invariants every later phase must keep are in [agent-plan/01-security-invariants.md](agent-plan/01-security-invariants.md).

## What the maintainer will do

Acknowledge a valid report, fix it on `main` or document the mitigation, and credit the reporter unless they ask to stay unnamed.
