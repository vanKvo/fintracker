# Data Pipeline — Current Logic Flow

Reflects the actual deployed state today: `services/fintracker-data-pipeline/infrastructure/terraform/modules/step_functions_pipeline/statemachine.asl.json.tpl`
and the environment's `main.tf`. Not a target/spec state — this is what runs.

Two separate entry points exist: the S3-triggered ingestion pipeline (Step Functions), and two
plain HTTP API Lambdas the pipeline pauses for / is polled through. Neither `JobStatus` nor
`MappingConfirmation` is itself a Step Functions task — they talk to the state machine only via
DynamoDB (shared status) and, for `MappingConfirmation`, by resolving Gatekeeper's paused task
token.

```mermaid
flowchart TD
    S3[("S3 statement bucket<br/>ObjectCreated event")] --> S3P[S3Processor Lambda]
    S3P -->|"validates via Ledger,<br/>writes initial job status,<br/>states:StartExecution"| SM

    subgraph SM[" Step Functions — FinTracker-DataPipeline-dev (STANDARD) "]
        direction TB
        GK["Gatekeeper<br/>(Task, waitForTaskToken)"] -->|"propose column mapping,<br/>pause for confirmation"| PAUSE{{"paused — task token held"}}
        PAUSE -->|"resumed by MappingConfirmation"| EX[Extractor]
        GK -->|"Catch: States.ALL"| FAIL1[["PipelineFailed (Fail)"]]
        EX -->|"Catch: NoValidTransactionsError"| FAIL2[["NoValidTransactions (Fail)"]]
        EX -->|"Catch: States.ALL"| FAIL1
        EX --> NM[Normalizer]
        NM -->|"Catch: States.ALL"| FAIL1
        NM --> LP[LedgerPush]
        LP -->|"Catch: States.ALL"| FAIL1
        LP --> DONE([End: success])
    end

    User(("User / Angular UI")) -->|"POST .../mapping-confirmation"| MC[MappingConfirmation Lambda]
    MC -->|"states:SendTaskSuccess<br/>(resumes Gatekeeper's token)"| PAUSE
    MC -->|"GetItem/PutItem"| JT[(JobTracker table)]
    MC -->|"GetItem/PutItem"| BM[(BankMapping table)]

    User -->|"GET .../jobs/{jobId}<br/>(polling, no WebSocket here)"| JS[JobStatus Lambda]
    JS -->|"GetItem"| JT

    GK -->|"PutItem status"| JT
    GK -->|"GetItem mapping"| BM
    EX -->|"PutItem status"| JT
    EX -->|"textract:AnalyzeDocument"| TX[[AWS Textract]]
    NM -->|"GetItem/PutItem"| MR[(MerchantRegistry table)]
    NM -->|"comprehend:ClassifyDocument"| CO[[AWS Comprehend classifier]]
    NM -->|"PutItem status"| JT
    LP -->|"PutItem status"| JT
    LP -->|"POST /transactions/internal/bulk"| LEDGER[["Ledger Service (external)"]]
```

## Notes on what's *not* here yet
- No `Retry` blocks anywhere in the ASL — every task's only error handling is a `Catch`
  straight to a terminal `Fail` state. A transient error (e.g. a Textract throttle) fails the
  whole job rather than retrying.
- `JobStatus` is polling-based; the pipeline spec's target design (per
  `data-pipeline-spec-01.md` / the root `CLAUDE.md`) is a WebSocket push via the User Profile
  Service on completion — not present in this flow because it isn't implemented in this pipeline
  yet.
- Both `MappingConfirmation` and `JobStatus` sit behind the same Cognito JWT HTTP API authorizer
  and overwrite `X-Internal-User-Id` from the JWT `sub` claim server-side — the client cannot
  supply or spoof it.
