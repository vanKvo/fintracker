# Fixes from temp_doc.md: implementation notes (2026-10-26)

Order asked for: H1, H2, C and H5, the Ledger internal API (H7), D, then the other gaps. E and F, and A and B after the deploy.

## Status

| Item | Result |
|---|---|
| H1 Status API 500 on Decimal | Fixed. Bug note: `docs/bugs/2026-10-26_bug_job_status_api_500_on_stored_duplicate_count.md` |
| H2 Raw dates sent to the Ledger (DP-ING-12) | Implemented in the pipeline and the Ledger owner lookup. DP-ING-12 is set to Implemented |
| C Wrong client hash (LG-STMT-08) | Implemented: the Ledger route `PATCH …/content-hash` and the Gatekeeper call. LG-STMT-08 is set to Implemented |
| H5 Cleanup leaves old versions (DP-ING-11) | Fixed. Bug note: `docs/bugs/2026-10-26_bug_page_image_cleanup_leaves_every_version_in_the_versioned_bucket.md`. DP-ING-11 is set to Implemented. The script has not been run in any environment |
| H7 Ledger internal API (LG-READ) | Implemented in the Ledger and the AI assistant. LG-READ-01 to -03 and AI-CHAT-05 are set to Implemented; LG-READ-04 stays In progress (see below) |
| D Remaining UI work | Built: low-confidence highlight, Statements-tab failure message, reason-code catalog (all codes in Appendix A), "This category is no longer available", "From your rule". XS-IMP-01, XS-IMP-04, XS-DPCAT-04 and XS-DPCAT-07 are set to Implemented |
| H3 Profile routes read a JWT sub | Fixed for the profile, settings, delete and goals routes. Bug note: `docs/bugs/2026-10-26_bug_profile_routes_read_jwt_claims_that_the_authorizer_never_sets.md` |
| H6 Chat doesn't stream | Only the authorizer part: it now answers REST API requests with an IAM policy (XS-CTX-02). Streaming itself is not done (below) |
| H4 Account deletion (XS-DEL) | Not started |
| E Not verified in AWS | Not done |
| F | Not done: temp_doc.md defines no item F |
| A Files to delete, B Ledger user-categories route | Not done: you said after the deploy, and A needs your approval per file |

## What was built

**Pipeline**
- `src/shared/dates.py`: one date parser (ISO, `M/D/YYYY`, `M/D/YY`, `M-D-YYYY`, `M-D-YY`, `M/D`, `M-D`). A date without a year takes the year that lies inside the statement's declared period; a period across New Year gives December the opening year and January the closing year.
- The Normalizer sends ISO dates only. A row whose date is unreadable or more than 7 days outside the period is skipped and counted (`skipped_count`); a statement with no readable date ends as `NO_VALID_TRANSACTIONS`. The Ledger push adds the skipped rows to `failedCount`/`totalCount`: a fully pushed statement with skipped rows is `PARTIALLY_COMPLETED` with no reason code (nothing failed at the Ledger).
- The period reaches the Normalizer through the S3 processor (from the Ledger owner lookup) and the Extractor output. The duplicate fingerprint uses the same parser.
- Gatekeeper: when the file's real hash matches nothing, it corrects the Ledger's stored hash (3 attempts). A 409 ends the import as `SERVER_DUPLICATE_DETECTED` with the matching statement; a failure after 3 attempts ends it as `PIPELINE_ERROR`.

**Ledger**
- The owner lookup returns `openingDate`/`closingDate`.
- `PATCH /statements/internal/{id}/content-hash`: 204 (also when repeated), 404 for another user's statement, 409 with the matching statement's details, 400 for a bad hash.
- `GET /transactions/internal/search` and `GET /budgets/internal/status` (LG-READ). The search totals come from window functions in the one query that returns the 25 rows. Budget status is a pure read (it creates nothing) and uses the Budgets tab's spend figure. The `/budgets/internal/*` prefix is under the caller filter.
- A database that cannot be reached (connection failure, timeout, SQLSTATE class 08, 53 or 57) answers 503 `database_unavailable` with `retryable = true` on every route, not only these two.

**AI assistant**: `search_transactions` and `get_budget_status` call the internal routes, one request each; the paging loop and `totals_complete` are gone.

**User Profile**: the authorizer answers REST `REQUEST` events with an Allow/Deny policy (resource = every method of the stage, for caching) and still answers HTTP API events with the simple response.

## Decisions to confirm

1. **MCP `list_transactions` changed.** LG-READ-01 says the AI assistant calls no public Ledger route, so the MCP tool now reads the internal search. It lost `account_id`, `status`, `page` and `size`, and returns spending only. No spec lists this tool. Say if you want it kept on the public route instead.
2. **`DELETE /profile` verifies the bearer token again to get the Cognito `sub`.** The authorizer context must stay at four fields (XS-CTX-02), and the identity mapping is keyed by `sub`. The service also refuses to delete unless that `sub` maps to the authorizer's user.
3. **`list_transactions`/`get_budget_status` month input.** The Ledger takes `YYYY-MM`; the client cuts a longer date to its month.

## Spec differences to resolve (specs are read-only for me)

- **LG-READ-01 / XS-CTX-04 say a rejected caller gets 403.** `InternalCallerFilter` answers 401 `missing-internal-caller` on every internal route, and its tests assert 401. I kept 401.
- **LG-READ-04: "no log contains the request's merchant text".** `logback-spring.xml` sets `org.jooq.tools.LoggerListener` to DEBUG in every profile, which logs bind values and result rows of every query. The routes' own log lines carry no merchant text and a test checks that, but the jOOQ logger breaks the rule app-wide. I did not change the logging level because it affects every environment.
- **LG-READ-04 load test** (10,000 transactions, p95 under 1 s) was not run.
- **DP-ING-12** says a skipped row is counted in `failedCount`. Rows with an unparsable *amount* are still dropped without being counted (existing behavior); say if the same rule should apply.
- **LG-STMT-08**: if the account's matching statement is a failed one with no transactions, the Ledger's lookups ignore it but the unique index does not, so the correction answers 500 and the import ends as `PIPELINE_ERROR`. The user uploads again and XS-IMP-03 clears the failed record.
- The test inventory rule allows nothing but F2P/P2P groups, so the LG-READ load test is not listed in `LG-READ-internal-read-routes-tests.md`; it is mentioned above instead.

## Not done, and why

- **H6 streaming.** There is no `chat-api` REST API, Lambda Web Adapter packaging or streaming integration anywhere in the repository, and ADR-012 decision 6 calls for a spike first. The AI assistant still runs under Mangum, which buffers. Under Lambda Web Adapter the `aws.event` that `core/identity.py` reads does not exist, so the user would come from the `x-amzn-request-context` header; whether a client can inject that header ahead of the adapter's own needs to be checked in the spike before the code trusts it. AI-CHAT-01 should stay as you have it ("should be In progress").
- **H4 XS-DEL.** It spans User Profile (grace period, scheduled hard deletion, Cognito calls, completion tracking), the Ledger (SQS consumer and deletion transaction), the pipeline (file, job and mapping deletion) and the event rules and queues. No SQS consumer or event rule for it exists yet. Proposed order when you want it: XS-DEL-07 (lifecycle rule, one Terraform change), then User Profile XS-DEL-01/02, then the Ledger and pipeline handlers, then XS-DEL-06.
- **E.** Needs AWS credentials and your approval for a `terraform plan` and a state-machine run against real accounts. Nothing here ran against AWS.

## Verification

| Suite | Result |
|---|---|
| Data pipeline (pytest) | 385 passed, 1 skipped, 1 xfailed |
| Ledger (Maven, Testcontainers) | 261 tests; one existing test (`InternalCallerFilterTest`, which pins the registered prefixes) needed the new budgets prefix and now passes. Not re-run as one full suite after that last edit |
| AI assistant (pytest) | 580 passed |
| User Profile (pytest) | 138 passed |
| UI (`ng test`) | 190 passed |
| UI `ng build` | Fails on the bundle budget: initial bundle 1.02 MB against the 1.00 MB error limit. I did not check whether it was already over before these changes |

## Process notes

- Tests were written before the code and seen failing for H1, H2 (pipeline), C (Ledger and pipeline), H5, LG-READ (Ledger), D (UI) and H3 and the REST authorizer (User Profile). Not seen failing first: the Ledger owner-period assertion, `DatabaseUnavailableHandlerTest` and the AI assistant's client tests. I wrote those with or before the code and ran them only afterwards.
- I ran `git checkout` on `InternalTransactionController.java` in the Ledger by mistake while moving the search route into its own controller. That file had an uncommitted change (the `packageId` argument); I restored it from the copy I had printed earlier, and the diff against HEAD is again the single changed line.


# temp_doc.md
#	Finding	Type	What is done, or what to give the developer
H1	Status API 500 on Decimal	Code bug	Fix against the LG-STMT Shared Contract, LG-STMT-04 and LG-STMT-08. I updated the contract to match DP-ING-10 (reason, not errorCode) and added a test entry to the XS-IMP tests file.
H2	Raw dates sent to the Ledger	Spec gap	New DP-ING-12: ISO dates, and the year taken from the declared statement period when the bank leaves it out. The 7-day tolerance is a default I proposed.
H3	Profile routes read a JWT sub	Code bug	Fix against UP-AUTH-02 A4/B1 (the authorizer type), XS-CTX-01 (saving settings) and the User Profile “Delete an account” flow.
H4	Account deletion	Spec gap	New XS-DEL spec: 30-day grace period, publish the event before removing the identity mapping, a Ledger handler, statement-file deletion, completion tracking and 7-day expiry of old file versions. I also updated the User Profile architecture steps to match.
H5	Cleanup leaves old versions	Both	The DP-ING-11 text was ambiguous, so I clarified it (every version, even when the original is gone) and set it back to In progress. Fix against DP-ING-11; test entries 44–45 show the expected behavior.
H6	Chat doesn’t stream	Code bug	Fix against AI-CHAT-01, ADR-012 decisions 1, 2, 4 and 6 (Lambda Web Adapter, REST API) and XS-CTX-02 (the authorizer must answer in REST format too). I didn’t change the status, but AI-CHAT-01 should be In progress.
H7	Chat calls public Ledger routes	Spec gap	New LG-READ spec: internal search and budget-status routes, with totals computed by the database. AI-CHAT-05 now points to it and is back to In progress.

# The implementation notes: 2026-10-25_xs_imp_import_reliability_implementation_notes and decisions.

Notes item	Recommendation	Covered by the 7?
1. Files to delete	Approve: src/categories/, tests/test_categories_client.py, bank_mapping_baseline.py, bank_mappings.json, and the test class that reads that JSON. Nothing uses them, and keeping them suggests the pipeline still holds a copy of the categories.	No, so it’s new item A
2. Ledger user-categories route	Retire it once the new pipeline is deployed in every environment. In the same change, remove its allow-list entry, the old pipeline’s permission to call it, and XS-DPCAT tests #22, #23 and #99.	No, so it’s new item B
3a. Two new reason codes; errorCode or reason	Done. XS-IMP Appendix A now has both codes and their messages. reason is the field name everywhere; I changed the LG-STMT contract to match earlier today.	Spec only
3b. Fingerprint described two ways	I agree with what was built (count, total, date range). The per-row version can never match across uploads, so LG-STMT-04 now describes the fingerprint only one way. One correction to the notes: “a CSV and a PDF of one period also match” isn’t true today, because only CSVs are fingerprinted. The same-month check usually catches that case at upload instead.	Spec only
3c. DP-MAP storage items	Done. Appendix A now lists the daily counters (kept 10 days) and the one-time promotion notice, and the Change Log records that the mapping proposal now takes the user id.	Spec only
3d. Duplicate question expiry	Done. LG-STMT-04 says the “already uploaded?” question expires after 30 minutes with DUPLICATE_RESOLUTION_TIMEOUT, and the statement becomes FAILED.	Spec only
3e. PARTIALLY_COMPLETED statement status	Done. XS-IMP-02 now says a partial import is a COMPLETED statement, and the job carries the counts.	Spec only
4. Wrong client hash	Now specced (above).	No, so it’s new item C
5. A failed push fails the run	Keep it. It’s the only way the Ledger hears about the failure (XS-IMP-02), and it’s what DP-ING-09 asks for. After the date fix (H2), every-row failures should be rare.	No action
Remaining UI work	Five UI pieces aren’t built: the low-confidence row highlight, the Statements-tab failure message, the reason-code message catalog (including the 2 new codes), “This category is no longer available”, and “From your rule”.	No, so it’s new item D
Run the page-image cleanup in each environment	Don’t run it until H5 is fixed. As written, it only adds delete markers and leaves every image in place.	H5
Not verified in AWS	Nothing has run in AWS: no state machine run, no terraform plan, alarms exist only in Terraform. This is the biggest risk in the notes.	No, so it’s new item E
Found on the way: proposal sent in snake_case	Already fixed.	