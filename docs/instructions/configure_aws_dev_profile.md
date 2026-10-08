# Configure an AWS CLI Dev Profile for the Data Pipeline

## Description
An AWS CLI **profile** (`~/.aws/config` / `~/.aws/credentials`) is just a named set of
credentials on your machine — it's how *you*, the developer, authenticate to run `aws`,
`terraform`, or `sam` commands against an account. It has nothing to do with how a *deployed*
service gets its permissions — that's the Lambda execution role Terraform creates per function
(see `configure_terraform_least_privilege` — the IAM audit is documented inline in
`services/fintracker-data-pipeline/infrastructure/terraform/environments/dev/main.tf`). This guide
only covers your local dev profile.

## Do you need a separate profile per microservice?
Not required, but it's the right default once more than one service has its own Terraform.
- A profile is just credentials pointing at an IAM identity (user, or a role you assume). What
  actually matters for blast-radius is the **policy attached to that identity**, not the profile
  name.
- Today only the Data Pipeline has Terraform (per the root `CLAUDE.md`, "Other services have no
  IaC of their own yet"), so one profile — `fintracker-data-pipeline-dev` — is enough for now.
- As Ledger/User Profile/Analytics gain their own Terraform, give each its **own IAM role/policy**
  scoped only to that service's resources (its own tables, buckets, functions — matching the
  `Service` tag each already sets, e.g. `Service = "data-pipeline"`), and a separate CLI profile
  per service that assumes that role. This means running `terraform destroy` inside one service's
  directory physically cannot touch another service's resources, even by mistake — the credentials
  in play don't have permission to.
- For a solo developer in one AWS account, this is about **mistake containment, not access
  control between people** — the value is a typo'd `terraform apply` in the wrong directory
  failing loudly instead of touching a different service's live resources.

## Guideline

### Step 1: Choose a credential source
Two supported paths — pick one:

**Option A — IAM Identity Center (SSO), recommended if your AWS account has it set up:**
```bash
aws configure sso --profile fintracker-data-pipeline-dev
# Prompts for SSO start URL, region, then lets you pick the account/permission set interactively.
```

**Option B — IAM user with access keys** (simpler for a single personal account with no SSO):
```bash
aws configure --profile fintracker-data-pipeline-dev
# AWS Access Key ID: <from an IAM user you create for this>
# AWS Secret Access Key: <...>
# Default region: us-east-1   # match services/fintracker-data-pipeline's aws_region tfvar
# Default output format: json
```
Create the IAM user first in the AWS Console (or `aws iam create-user`) and attach a policy scoped
to what Terraform needs to create/manage for this service — see Step 2.

### Step 2: Scope the underlying IAM identity, not just the profile
Whatever identity Step 1 points at needs permission to create/manage: Lambda functions & their
IAM roles, DynamoDB tables, the S3 statement bucket, the Step Functions state machine, and the
HTTP API Gateway — i.e. every resource type under
`services/fintracker-data-pipeline/infrastructure/terraform/`. For a solo dev project, the
pragmatic options, in order of preference:
1. A custom policy whose `Resource` entries are scoped to names/ARNs prefixed `FinTracker*` /
   `fintracker-*` (matching this service's actual resource names) plus a `Condition` requiring the
   `Service = "data-pipeline"` tag on tag-aware actions — real least privilege, more setup.
2. AWS managed **`PowerUserAccess`** — broad but deliberately excludes IAM user/policy management
   (so it can't be used to escalate its own privileges), a common pragmatic choice for a personal
   dev account. Terraform still needs `iam:CreateRole`/`PutRolePolicy` for the Lambda execution
   roles it manages, so pair it with a narrow custom IAM-management statement scoped to role names
   like `FinTracker-DataPipeline-dev-*-role`.
- Avoid attaching full `AdministratorAccess` to a long-lived local profile — it defeats the point
  of having a named dev profile at all.

### Step 3: Verify the profile
```bash
aws sts get-caller-identity --profile fintracker-data-pipeline-dev
```
Confirms which account/identity the profile actually resolves to before you point Terraform at it.

### Step 4: Use it
Either export it for the shell session:
```bash
export AWS_PROFILE=fintracker-data-pipeline-dev
cd services/fintracker-data-pipeline/infrastructure/terraform/environments/dev
terraform plan
```
or pass it explicitly per Terraform run, since `aws_profile` is already a declared input
(`variables.tf`):
```bash
terraform plan -var="aws_profile=fintracker-data-pipeline-dev"
```
