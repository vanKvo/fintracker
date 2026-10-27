# FinTracker Error Catalog

| Status | Owner | Last reviewed | Applies to | App architecture |
|---|---|---|---|---|
| Current | Van Vo | 2026-10-23 | main | [FinTracker architecture 4.8](fintracker-architectural-doc.md#48-report-what-does-a-failure-look-like-to-the-user-and-to-the-developer) |

Every error code a client can receive, from every service. The app doc (4.8) sets the rules; this file lists the codes.

**How to use it:**
- The UI chooses its message by `code`. For a code it doesn't know, it shows `detail`, which is always safe for users.
- A code is a contract. It is never renamed or reused. A retired code is marked *Deprecated* and stays listed.
- Adding a code means adding its row here in the same pull request. Each service's tests check that its codes are unique and snake_case.
- Generic codes are defined once, under Shared codes, and every service uses them with the same meaning. Business codes are specific enough not to collide (`budget_closed`, not `closed`).
- **Retryable** means the same request can succeed shortly. The UI may offer "Try again" or retry a read once (UI-CORE-01). A 429 or 503 may include `Retry-After`.

---

## 1. Shared codes

| Code | HTTP | Retryable | Meaning | What the user sees or does |
|---|---|---|---|---|
| `invalid_argument` | 400 | No | A parameter or body field fails validation. `detail` names the fields, never the values | Fix the named field |
| `unauthorized` | 401 | No | No verified user on a public route | Sign in again |
| `not_found` | 404 | No | The route doesn't exist, or the resource isn't the caller's (cross-tenant reads return 404, invariant 5) | Nothing to retry |
| `method_not_allowed` | 405 | No | The route exists but not for this method | Client bug; nothing to retry |
| `user_settings_incomplete` | 409 | No | A route needs the timezone and the user hasn't set one (XS-CTX-05) | Set the timezone in Settings |
| `invalid_setting` | 400 | No | A settings save has an invalid value (XS-CTX-01) | Fix the value |
| `timeout` | 504 | Yes (reads) | The request ran past its deadline | Try again |
| `service_unavailable` | 503 | Yes | A dependency is down | Try again in a moment |
| `database_unavailable` | 503 | Yes | Aurora failed after one retry, including a cold resume in dev | Try again; reads retry once automatically (UI-CORE-01) |
| `user_context_invalid` | 500 | No | A context value is present but invalid, or the currency is missing (XS-CTX-05). Alarms on the first occurrence | "We couldn't read your settings. The error has been recorded." |
| `internal_error` | 500 | No | Anything unexpected | "Something went wrong on our side. The error has been recorded. Please try again later." plus the reference (`trace_id`) |

## 2. Internal-only codes (service to service)

Returned on internal APIs only. The calling service maps them to its own error and never passes them through to the user.

| Code | HTTP | Service | Meaning |
|---|---|---|---|
| `user_context_missing` | 401 | Knowledge | A signed request without a forwarded user context (KN-RET-01) |
| `caller_not_allowed` | 403 | Knowledge | The caller's IAM role isn't on the allow-list (KN-RET-01) |
| `scope_not_enabled` | 400 | Knowledge | `scope = mine` before KN-UDOC ships (KN-RET-02) |
| `embedding_unavailable` | 503 | Knowledge | Bedrock embedding failed after retries (KN-RET-03) |

## 3. Codes by service

### AI assistant

Source: `src/core/exceptions.py`, `src/summary/exceptions.py`, `src/chat/schemas.py` (`ChatErrorCode`), `src/chat/fallback.py` (`ERROR_MESSAGES`).

| Code | HTTP | Retryable | Meaning | What the user sees or does |
|---|---|---|---|---|
| `summary_unavailable` | 503 | Yes | The facts or the refresh counter couldn't be read, so there is no summary (FS-13) | "We couldn't load your summary right now. Please try again in a moment." |
| `refresh_limit_reached` | 429 | No | The daily refresh allowance is used up (FS-14) | "You can refresh your summary {limit} times a day. Try again tomorrow." (limit is 5 today) |

**Chat stream** (AI-CHAT Appendix A). Once the stream has started, these codes arrive in its `error` event, not as an HTTP error, and use the same meanings. A bad request body is a 400 `invalid_argument` and an unknown or another user's conversation a 404 `not_found`, both before the stream starts:

| Code | Retryable | Meaning |
|---|---|---|
| `daily_limit_reached` | No | The tier's daily token allowance is used up; the event carries `reset_at`, the next midnight in the user's timezone |
| `limits_unavailable` | Yes | The usage counter or the spend budget couldn't be read or updated, or no allowance is configured for the tier, so the turn ends (limits never fail open) |
| `service_busy` | Yes | Too many turns in flight, the model is throttled or unavailable, or the app-wide daily budget is used up (shared with the Financial Summary) |
| `timeout`, `invalid_argument`, `internal_error` | — | As in Shared codes (`timeout`: the 45 s turn deadline or the model call timed out) |

### Analytics

| Code | HTTP | Retryable | Meaning |
|---|---|---|---|
| `invalid_argument` | 400 | No | Unknown period key or an extra query parameter (AN-RPT-03) |
| `user_settings_incomplete` | 409 | No | As shared |
| `database_unavailable` | 503 | Yes | As shared (XS-RPTV-07) |

### Knowledge

Shared codes `invalid_argument`, `database_unavailable`, `timeout` and `internal_error`, plus the internal-only codes in section 2. The AI assistant treats every Knowledge error as "no docs available" (KN-RET-07).

### Document service

Shared codes `unauthorized`, `not_found`, `service_unavailable` and `internal_error`, plus:

| Code | HTTP | Retryable | Meaning | What the user sees or does |
|---|---|---|---|---|
| `document_not_ready` | 409 | No | The file is still in quarantine or failed its malware scan; no download link is issued (DS-DL-01) | Wait for the upload to finish, or upload again |

### Ledger *(to adopt: sends `type` today, no `code`)*

The Ledger's problem types today, from `GlobalExceptionHandler` (snapshot of 2026-10-20; check against the current file when adopting). Each becomes the code shown, by replacing hyphens with underscores. Merges are marked.

| Code | HTTP | Meaning |
|---|---|---|
| `invalid_argument` | 400 | Today's `invalid-argument`, `invalid-parameter`, `invalid-request`, `missing-parameter` and `validation-error` (merge into the shared code) |
| `invalid_budget` | 400 | The budget payload is invalid |
| `invalid_category_name` | 400 | The category name is invalid |
| `category_limit_exceeded` | 400 | Too many custom categories |
| `line_item_limit_exceeded` | 400 | Too many budget line items |
| `system_category_immutable` | 400 | A system category can't be changed |
| `not_found` | 404 | Today's `not-found`, `endpoint-not-found` and `resource-not-found` (merge into the shared code) |
| `transaction_not_found` | 404 | No such transaction for this user |
| `statement_not_found` | 404 | No such statement for this user |
| `bill_not_found` | 404 | No such bill for this user |
| `category_not_found` | 404 | No such category for this user |
| `method_not_allowed` | 405 | As shared |
| `category_already_exists` | 409 | A category with that name exists |
| `duplicate_category` | 409 | The category is already in this budget |
| `category_in_use` | 409 | The category can't be deleted while transactions use it |
| `duplicate_template` | 409 | A budget template with that name exists |
| `duplicate_statement` | 409 | The statement was already uploaded; carries `matchType`, `existingStatementId`, `existingUploadDate`, `existingTransactionCount` (LG-STMT-03) |
| `illegal_state_transition` | 409 | The transaction's status can't change that way |
| `historical_budget` | 422 | A write to a closed budget |
| `split_amount_mismatch` | 422 | Split amounts don't add up to the transaction |
| `too_many_tags` | 422 | Over the tag limit |
| `internal_error` | 500 | As shared |

### Data pipeline *(async: codes reach the user through the import status, not an HTTP error)*

Source: `src/shared/exceptions.py` (`reason`). Stored in upper case on the Job Tracker today; the status API is to return them in lower case, as below. The user actions are proposed until DP-ING confirms them.

| Code | Retryable | Meaning | What the user does *(proposed)* |
|---|---|---|---|
| `unsupported_format` | No | The file isn't a supported PDF or CSV | Upload a PDF or CSV statement |
| `file_too_large` | No | Over the size limit | Upload a smaller file |
| `too_many_pages` | No | Over the page limit | Split the statement |
| `no_valid_pages` | No | No page could be read | Upload a clearer copy |
| `invalid_csv_format` | No | The CSV can't be parsed | Export the CSV again from the bank |
| `csv_row_parse_error` | No | One or more rows can't be parsed | Check the file and upload again |
| `no_valid_transactions` | No | Processed, but no transactions found | Check that it's a statement |
| `csv_col_mapping_confirmation_timeout` | No | The column mapping wasn't confirmed in time | Upload again and confirm the mapping |
| `unknown_bank_mapping` | No | No mapping for this bank where one was required | Map the columns |
| `statement_owner_not_found` | No | The Ledger has no record of the statement; never retried (REQ-DP-05) | Upload again |
| `categories_unavailable` | Yes | The Ledger's categories couldn't be read | Retried by the pipeline |
| `ledger_push_failed` | Yes | The transactions couldn't be written to the Ledger | Retried by the pipeline |
| `ledger_not_configured` | No | Deployment error | Internal; the user sees `internal_error` |
| `pipeline_error` | No | Anything else | Internal; the user sees `internal_error` |

---

## 4. Adoption status

| Service | Problem+json with `code` and `trace_id` | One generic handler | 5xx traceback logged | Gaps |
|---|---|---|---|---|
| AI assistant | Yes | Yes | Yes, library messages redacted | None |
| Analytics | Yes | Yes | Yes, library messages redacted | None |
| Ledger | Partly: `type`, no `code` or `trace_id`; type base is `https://api.fintracker.com/problems/` | No: one method per exception | Yes | 4xx `detail` is `ex.getMessage()`; database errors log `ex.getMessage()`, which can carry SQL bind values |
| Knowledge | Yes (KN-RET App. C) | Yes: `core/error_handlers.handle_error`, called by each Lambda handler (no web framework) | Yes, library messages redacted | No `ServerError` metric yet: 5xx is counted by the retrieval request metric's error code (KN-RET-08) |
| Document service | Yes | Yes: `core/error_handlers.handle_error`, called by each Lambda handler | Yes, library messages redacted | None |
| XS-CTX | Yes (App. C) | n/a (spec) | n/a | None |
| Data pipeline | n/a (async) | n/a | — | Return lower-case codes from the status API |
