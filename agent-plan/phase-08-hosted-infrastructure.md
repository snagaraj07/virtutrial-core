# Phase 8 — Hosted infrastructure

```yaml
id: "08"
status: blocked
depends_on: ["07"]
```

## Goal

A study team can read one Terraform layout and see every network and encryption boundary before they apply it in their own account.

## In scope

`deploy/aws/` modules and a root stack wired by variables. Documentation of what the human must supply. No apply step.

## Out of scope

Running Terraform, creating cloud resources, and storing state in this repository. CI must not call a cloud API.

## Security

S3 and S7. No account id, no key, and no real CIDR that belongs to a private network unless the human adds it locally in a gitignored `terraform.tfvars`. Commit only `terraform.tfvars.example` with placeholders `REPLACE_ACCOUNT_ID`, `REPLACE_CIDR`, and `REPLACE_OIDC_ISSUER`. Public access block is on for the bucket. The database has no public route. The task role can read its secret and its study prefix, and cannot administer IAM.

## Deliverables

| Path | Purpose |
| --- | --- |
| `deploy/aws/README.md` | Human apply steps and the boundary table |
| `deploy/aws/versions.tf` | Required Terraform and AWS provider versions |
| `deploy/aws/variables.tf` | Account, region, CIDR allow list, OIDC issuer, name prefix |
| `deploy/aws/main.tf` | Wires the modules below |
| `deploy/aws/terraform.tfvars.example` | Placeholders only |
| `deploy/aws/modules/network/` | VPC, private subnets, no public database subnet route |
| `deploy/aws/modules/storage/` | Bucket, KMS key, public access block |
| `deploy/aws/modules/metadata/` | Postgres subnet group and security group |
| `deploy/aws/modules/service/` | Container service, load balancer, task role, secret references |

## Steps

1. Write modules that match the table in `00-system-design.md`.
2. Bucket: `block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets` all true. Server-side encryption uses the module's KMS key.
3. Database security group allows ingress only from the app security group on 5432.
4. Load balancer listens on 443. The app security group allows the app port only from the load balancer security group.
5. Task role policy statements are explicit. Resource ARNs are the study bucket prefix and the secret ARNs. No `Action = "*"`.
6. `terraform.tfvars` and `*.tfstate` stay gitignored. The example file uses the placeholders above.
7. `deploy/aws/README.md` tells the human to copy the example, fill it outside git, run `terraform plan`, and apply themselves. State the team's identity provider and cloud agreement stay with the team.
8. Add a CI step or a local test that `git grep -n REPLACE_ACCOUNT_ID` finds the example file and that `git ls-files` does not list a `tfstate` or a real `tfvars`.

## Interfaces

Terraform variables:

```text
name_prefix
aws_region
vpc_cidr
allowed_ingress_cidrs
oidc_issuer
db_name
```

No variable default may be a real account id or a live secret.

## Tests

From the repository root:

```bash
git ls-files '*.tfstate' '*.tfvars' | grep -q . && exit 1 || exit 0
test -f deploy/aws/terraform.tfvars.example
grep -q REPLACE_ACCOUNT_ID deploy/aws/terraform.tfvars.example
grep -q block_public_policy deploy/aws/modules/storage/*.tf
```

If the Terraform CLI is installed, also run `terraform fmt -check -recursive deploy/aws` and `terraform validate` in `deploy/aws` after `terraform init -backend=false`. Skip validate with a printed reason when the CLI is absent. Do not run `terraform apply`.

## Done when

The file checks pass, phase 08 is `complete`, and phase 09 is `ready` if phase 03 is complete. If phase 03 is not complete, leave phase 09 blocked.

## Do not

Do not run `terraform apply`. Do not add a GitHub secret for cloud credentials. Do not commit state or a filled-in tfvars file.
