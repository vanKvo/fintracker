# Data Pipeline — IAM Roles & Permissions

Reflects `services/fintracker-data-pipeline/infrastructure/terraform/environments/dev/main.tf` +
`modules/lambda_function/main.tf` + `modules/step_functions_pipeline/main.tf` as deployed today.
Every Lambda gets its **own** IAM role (no sharing) — that part is already correct
least-privilege practice; the diagram below shows what each role can actually touch.

```mermaid
flowchart LR
    subgraph Roles [" One IAM role per Lambda, each also gets AWSLambdaBasicExecutionRole (logs:*) "]
        RGK["Gatekeeper-role"]
        REX["Extractor-role"]
        RNM["Normalizer-role"]
        RLP["LedgerPush-role"]
        RS3["S3Processor-role"]
        RJS["JobStatus-role"]
        RMC["MappingConfirmation-role"]
        RSF["StepFunctions-role"]
    end

    RGK -->|"s3:GetObject"| BUCKET[("Statement S3 bucket")]
    RGK -->|"dynamodb:PutItem"| JT[(JobTracker table)]
    RGK -->|"dynamodb:GetItem"| BM[(BankMapping table)]
    RGK -.->|"states:SendTaskSuccess/Failure — Resource: * (deliberate: token-scoped, not ARN-scoped)"| SFN[["Step Functions state machine"]]

    REX -->|"s3:GetObject, s3:PutObject"| BUCKET
    REX -->|"textract:AnalyzeDocument — Resource: * (Textract has no resource-level ARNs)"| TX[[AWS Textract]]
    REX -->|"dynamodb:PutItem"| JT

    RNM -->|"dynamodb:GetItem, PutItem"| MR[(MerchantRegistry table)]
    RNM -->|"dynamodb:PutItem"| JT
    RNM -->|"comprehend:ClassifyDocument — scoped to one classifier-endpoint ARN"| CO[[AWS Comprehend]]

    RLP -->|"dynamodb:PutItem"| JT
    RLP -.->|"HTTPS (app-level, not IAM)"| LEDGER[["Ledger Service"]]

    RS3 -->|"s3:GetObject"| BUCKET
    RS3 -->|"states:StartExecution — scoped to this state machine's ARN"| SFN
    RS3 -->|"dynamodb:PutItem"| JT

    RJS -->|"dynamodb:GetItem"| JT

    RMC -.->|"states:SendTaskSuccess — Resource: * (same token-scoping reason)"| SFN
    RMC -->|"dynamodb:GetItem, PutItem"| JT
    RMC -->|"dynamodb:GetItem, PutItem"| BM

    RSF -->|"lambda:InvokeFunction — 4 explicit function ARNs (Gatekeeper/Extractor/Normalizer/LedgerPush)"| Roles
    RSF -.->|"logs:CreateLogDelivery + friends — Resource: * (AWS-required for Step Functions vended logging, not scopable)"| CW[[CloudWatch Logs]]

    classDef gk fill:#fde3e3,stroke:#e6194b,color:#7a0d0d
    classDef ex fill:#e2f6e6,stroke:#3cb44b,color:#1a5c2b
    classDef nm fill:#e3e9fb,stroke:#4363d8,color:#1c2f7a
    classDef lp fill:#fde9d9,stroke:#f58231,color:#8a4400
    classDef s3p fill:#f1e0f7,stroke:#911eb4,color:#4a0a63
    classDef js fill:#dff5f5,stroke:#469990,color:#1f4d4d
    classDef mc fill:#fbe0f6,stroke:#f032e6,color:#7a1a6d
    classDef sf fill:#f0ead6,stroke:#9a6324,color:#4d3210
    class RGK gk
    class REX ex
    class RNM nm
    class RLP lp
    class RS3 s3p
    class RJS js
    class RMC mc
    class RSF sf

    linkStyle 0,1,2,3 stroke:#e6194b,stroke-width:2px
    linkStyle 4,5,6 stroke:#3cb44b,stroke-width:2px
    linkStyle 7,8,9 stroke:#4363d8,stroke-width:2px
    linkStyle 10,11 stroke:#f58231,stroke-width:2px
    linkStyle 12,13,14 stroke:#911eb4,stroke-width:2px
    linkStyle 15 stroke:#469990,stroke-width:2px
    linkStyle 16,17,18 stroke:#f032e6,stroke-width:2px
    linkStyle 19,20 stroke:#9a6324,stroke-width:2px
```

Each role has one color, applied to both its box (fill) and every edge leaving it — trace a
single role's reach by following one color instead of untangling black lines. Solid vs. dashed
still marks scoped vs. wildcarded, independent of color.

## Findings

| # | Severity | Where | Issue |
|---|---|---|---|
| 1 | Informational | `Gatekeeper-role`, `MappingConfirmation-role`: `states:SendTaskSuccess`/`SendTaskFailure` on `Resource: "*"` | Comment in `main.tf` explains this is deliberate — a `waitForTaskToken` resume is authorized by the token itself, not the state machine ARN, so AWS doesn't offer a tighter `Resource` to scope to. Worth a periodic recheck against current AWS docs, but not a misconfiguration as written. |
| 2 | Informational | `StepFunctions-role`: `logs:CreateLogDelivery`/`GetLogDelivery`/`UpdateLogDelivery`/`DeleteLogDelivery`/`ListLogDeliveries`/`PutResourcePolicy`/`DescribeResourcePolicies`/`DescribeLogGroups` on `Resource: "*"` | Required, AWS-documented pattern for Step Functions execution logging — these specific log-delivery actions don't support resource-level restriction. Not a repo-introduced gap. |
| 3 | Not a finding | `Extractor-role`: `textract:AnalyzeDocument` on `Resource: "*"` | Textract has no resource-level permissions at all; the action itself is already minimal (one action, not `textract:*`). |
| — | Good practice | Every DynamoDB/S3 statement across all 8 roles | Single specific actions (`GetItem`/`PutItem`, `GetObject`/`PutObject`) scoped to one table/bucket ARN each. No `dynamodb:*`, `s3:*`, or `iam:PassRole` grant found anywhere in this service's Terraform. |

**Bottom line: yes, Terraform already configures least privilege for these Lambdas**, to the
extent AWS's own API surface allows. The only `Resource: "*"` grants are cases where AWS itself
doesn't expose a narrower resource to scope to (task-token-authorized Step Functions calls,
Step-Functions-vended logging, and Textract) — not wildcards this repo chose out of convenience.
