# 1. User Profile Service
This service manages the synchronous, high-read operations required to bootstrap the application and manage the user lifecycle. It leverages AWS Cognito exclusively for authentication and session management.

## Module: User Management & Authentication
### 1.1. Workflow: User Registration & Federation
- **Execution:** Handled entirely by Cognito Hosted UI / Amplify Auth. Maps standard email/password or Google Identity logins into a single identity pool.
- **Backend Sync (Post-Confirmation):** A Cognito Post-Confirmation Lambda Trigger listens for first-time sign-ups (or first-time Google logins) and initializes the base `USER#<user_id>` `PROFILE` and `SETTINGS` records in the FinTracker_UserProfile DynamoDB table.

### 1.2. Workflow: User Login & Session Management
- **Execution:** User authenticates via Cognito or Google identity. Frontend receives JWT tokens.
- **Authorization:** API Gateway validates the JWT via a Cognito Authorizer before routing requests to backend services.
- **Security:** Password resets and MFA setup (e.g., OTP) are natively orchestrated by Cognito forms/APIs natively without custom backend management.

## Module: Profile & Preferences
### 1.3. Workflow: Fetch Profile and Settings
- Client calls `GET /profile/settings` supplying their JWT.
- API Gateway passes the verified JWT `sub` as the `user_id`.
- The service executes a single `Query` to DynamoDB (`PK = USER#<user_id>`) fetching both `PROFILE` and `SETTINGS` to bootstrap the application instantly.

### 1.4. Workflow: Account Offboarding (Deletion)
- **Execution:** User requests account deletion.
- **Process:** The service disables the user in Cognito, drops all `USER#<user_id>` records from the DynamoDB table, and publishes an `AccountDeleted` event to EventBridge/SQS to trigger asynchronous deletion of ACID financial records in the `ledger-service`.

## Module: Static Financial Goals
### 1.5. Workflow: Manage Savings Goals
- Provides target amounts and deadlines used to calculate the "Safe to Spend" metric on the Dashboard View.
- Executes CRUD operations against the DynamoDB table utilizing the `begins_with(SK, 'GOAL#')` query pattern.

## Module: Notification Service & API WebSockets
### 1.6. Workflow: Manage Real-Time Updates
- Tracks long-lived API Gateway WebSocket connections (`WS#<connection_id>`) attached to the `user_id`.
- Enables pushing domain events (like Statement Processed or Budget Alert) directly to UI clients without coupling Data Pipeline to sockets.
- 
# 2. Data Pipelines Service
This service operates as the asynchronous ingestion engine, optimized for event-driven, compute-intensive background processing.
## Module: The "Statement Upload" Pipeline
### 2.1. Workflow: Process PDF/CSV Uploads
- **Trigger**: S3 File Upload.
- **Step 1**: Call Vision Gatekeeper to check if the image has a table. If PDF, split into images. Run YOLOv8-Nano (Inference) on the backend to confirm the frontend's "Table Detected" signal (Secondary Verification). Output: A manifest of "Valid Transaction Pages" vs. "Junk Pages."
- **Step 2**: Decision Gate (Step Function Choice). Condition: Are there valid transaction pages? Yes: Proceed to Step 3. No: Terminate workflow; move file to archived/junk and notify User via WebSocket (Identity Service) that the document contained no readable transactions.
- **Step 3**: Document Ingestion (AWS Textract).
- **Step 4**: Call Normalizer. Apply basic Regex Map for obvious patterns (e.g., ^uber.* -> Transportation). Search for merchant category in the `FinTracker_MerchantRegistry` DynamoDB table. If merchant is not found, call Categorizer.
- **Step 5**: Push all transactions to Ledger (PostgreSQL) with `PENDING` status.
- Updates the `JOB#<step_func_id>` status in DynamoDB to track the asynchronous pipeline state.

# 3. Ledger Service
This service functions as the synchronous, ACID-compliant System of Record for all core financial data.
## Module: Transactions
### 3.1. Workflow: Fetch and Filter Ledger Data
- Populates the Transactions View data table and dynamic "Total Amount" aggregations.
- Queries the ledger.transactions table, utilizing the idx_tx_account_date index for optimized retrieval.
- Applies multi-select filters including merchant text, date ranges, categories, tags, and status.
### 3.2. Workflow: Execute Row-Level and Bulk Actions
- Updates existing rows in ledger.transactions to modify categories, amounts, or dates, and appends values to the multi-select tags text array.
- Creates new database rows linked via parent_transaction_id when a user triggers a Split Transaction.
- Toggles the is_excluded boolean flag to hide synced records from budget calculations without deleting the immutable row.
- Updates the status column from 'PENDING_APPROVAL' to 'POSTED' when transactions are approved.
### 3.3. Workflow: Manage Manual Entries
- Inserts new rows into ledger.transactions with the source strictly set to 'MANUAL_ENTRY'.
- Enables the hard-delete UI button only when the database validates that the is_manual flag is true.
## Module: Budgets
### 3.4. Workflow: Manage Time-Series Budgets
- Populates the visual pacing indicators and category progress bars on the Budgets View.
- Creates or updates records in ledger.budgets and ledger.budget_lines, locking the effective_month to the first of the month.
- Enforces a strict read-only state for past months to ensure historical integrity.
- Generates a base template automatically by copying categories and limits from the previous month if a user navigates to a month without an existing budget.
## Module: Statement Metadata
### 3.5. Workflow: Manage Vault Documents
- Fetches metadata from ledger.statements to populate the Statement Table, including upload status and linked accounts.
- Powers the visual completeness grid by checking ledger.statements for missing statement_month entries.
- Executes hard deletions of statements, which relies on the ON DELETE CASCADE constraint to automatically remove all associated ledger transactions.
## Module: Accounts & Dashboard Actions
### 3.6. Workflow: Manage Upcoming Bills
- Populates the chronological list of fixed expenses on the Dashboard View by querying ledger.upcoming_bills where the status is 'ACTIVE'.
### 3.7. Workflow: Track Paid Bills
- Creates records in ledger.bill_payments when a user triggers the "Mark as Paid" action in the Bills Tab. Updates visual Status Indicators based on whether the current month has an existing payment record.
### 3.8. Workflow: Action Hub & Alert Generation
- Queries ledger.bank_connections to flag accounts with a 'NEEDS_RECONNECT' or 'REVOKED' status.
- Identifies pending transactions awaiting review and specific budget categories where current spending exceeds the limit_amount in ledger.budget_lines.

# 4. Analytics Service
This service acts as the read-only, OLAP business intelligence engine running against a PostgreSQL Read Replica to prevent degradation of real-time transactions.
## Module: Dashboard Aggregations
### 4.1. Workflow: Calculate 3-Second Overview
- Aggregates total balance, monthly income, monthly expenses, and net savings for the Dashboard Financial Overview Cards.
- Computes the mathematically calculated "Safe to Spend" metric by subtracting active upcoming bills, pending transactions, and static savings goals from the user's available cash.
## Module: Financial Reports & Spending Insights
### 4.2. Workflow: Generate Historical Visualizations
- Queries historically posted transactions using the idx_tx_status_date index to generate data for Spending Category pie charts and interactive drill-downs on the Reports View.
- Calculates Cash Flow Trends, Year-over-Year comparisons, and Month-over-Month metrics based on the selected time range filter.
- Provides the average monthly expense calculation required to power the interactive Emergency Fund Calculator widget.
- Generates total actual spending versus total budget limit vectors for the Dashboard Line Graph.
### 4.3. Workflow: AI Anomaly & Insight Generation
- Executes backend LLM analysis to scan historical transaction patterns.
- Flags potential hidden price increases in recurring services (Subscription Creep).
- Alerts the user to unusual spending spikes that deviate from their historical baseline averages.

