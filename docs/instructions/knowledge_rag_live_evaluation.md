# Run the Live RAG Evaluation (KN-CHUNK-05)

## Description
How the repo owner runs the paid live RAG evaluation of the Knowledge service (`services/fintracker-knowledge`): check the cost, approve, record new embedding vectors with Bedrock, score retrieval, and commit the refreshed snapshot after a pass. Only the repo owner runs it; AI agents never do.

## Guideline

### Step 1: One-time prerequisites
1. **An AWS profile of your own** with `bedrock:InvokeModel` on Titan Text Embeddings V2 in `us-east-1`, and write access to the results bucket (`RAG_EVAL_RESULTS_BUCKET`).
2. **Docker running.** The live run indexes into a throwaway pgvector database that Testcontainers starts itself. Your local database is not used.
3. **No static AWS credentials in the shell.** Unset `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` and `AWS_PROFILE`. The run refuses to start if any of them is set; it uses only the profile you name.

### Step 2: Check the plan and the cost (free)
```bash
cd services/fintracker-knowledge
poetry install
poetry run python -m src.rag_eval dry
```
It prints how many texts it would embed, how many are already in the committed recording (free), how many paid calls it would make, and the estimated and worst-case cost. Nothing is called and nothing is written.

### Step 3: Run it
```bash
AWS_REGION=us-east-1 RAG_EVAL_RESULTS_BUCKET=<bucket> \
  poetry run python -m src.rag_eval live --aws-profile <your-profile>
```
- The run shows the same plan and asks you to type `I approve N`, where N is the number of paid calls. Anything else stops it before any call.
- The default cost cap is $0.50. If the worst case is above the cap, the run stops; raise `--cap-usd` and add `--confirm-over-cap` only if you accept that spend.
- `--fresh` ignores the recorded vectors and pays for all of them again. Leave it off normally.
- The run refuses under pytest, when an AI agent's environment marker is set, without a terminal, and when it is not given a profile.

### Step 4: Read the result
The run prints recall@5, hit@1, hit@3, MRR, the gate (`pass` or `fail`), each golden question's first expected rank, and a threshold table. The full report is written to `services/fintracker-knowledge/eval/rag_eval_results/` (git-ignored).

- **Pass:** `tests/fixtures/rag/` (the recording, the corpus snapshot and the baseline) is replaced, and a pass record is saved to the results bucket. Continue to Step 5.
- **Fail:** the committed fixture and baseline are not changed, and no pass record is written. Fix the cause and run again. A rerun reuses only the vectors already in the committed recording.
- **Stopped** (cost cap, approval refused, a Bedrock error): nothing is changed; a stopped run leaves no report that looks like a pass.

### Step 5: Commit the refreshed snapshot
Commit the refreshed `tests/fixtures/rag/` after a pass. A pull request that changes the chunker, the embedded text, the retrieval query, the golden set or the recording is blocked by the `eval-required` check until a pass exists for its exact version. A pass for an older version does not count.

### Alternative: the manual `rag-eval` workflow
Run it from GitHub Actions: **Actions → RAG evaluation (live) → Run workflow**, and set `cap_usd` if needed. The job waits for your approval in the protected `rag-eval` environment (you are its required reviewer) before it receives the AWS role. It runs the same command as Step 3 and uploads `tests/fixtures/rag/` and the report as the artifact `rag-eval-fixture-and-report`. After a pass, download the artifact, copy `tests/fixtures/rag/` into your checkout, and commit it as in Step 5.

The Terraform for the results bucket, the OIDC role and the environment is described in `services/fintracker-knowledge/infrastructure/terraform/README.md`.
