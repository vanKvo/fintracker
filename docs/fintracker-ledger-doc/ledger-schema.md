# Ledger Service (PostgreSQL)
**Engine:** Amazon Aurora Serverless v2 (PostgreSQL)
**Schema:** `ledger`

```sql
CREATE SCHEMA IF NOT EXISTS ledger;

-- ==========================================
-- TABLE: bank_connections
-- Domain: Manages Teller.io integrations. Decoupled from accounts to allow 
-- seamless downgrade to 'Manual' mode without deleting historical data.
-- ==========================================
CREATE TABLE ledger.bank_connections (
    connection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL, -- Maps to Cognito/DynamoDB User ID
    teller_enrollment_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('ACTIVE', 'NEEDS_RECONNECT', 'REVOKED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- TABLE: accounts
-- Domain: The actual financial buckets (Checking, Savings, Credit).
-- ==========================================
CREATE TABLE ledger.accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    connection_id UUID REFERENCES ledger.bank_connections(connection_id) ON DELETE SET NULL,
    external_account_id VARCHAR(255), -- Teller's internal ID
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('CHECKING', 'SAVINGS', 'CREDIT')),
    current_balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    sync_mode VARCHAR(20) NOT NULL CHECK (sync_mode IN ('MANUAL', 'AUTOMATED')),
    last_watermark_date TIMESTAMP WITH TIME ZONE, -- Prevents duplicate fetching when switching modes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- TABLE: statements
-- Domain: Metadata for manually uploaded PDFs or CSVs.
-- ==========================================
CREATE TABLE ledger.statements (
    statement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES ledger.accounts(account_id) ON DELETE CASCADE,
    s3_object_key VARCHAR(1024) NOT NULL,
    statement_month DATE NOT NULL, -- 1st of the month the statement covers (e.g., '2026-03-01')
    status VARCHAR(50) NOT NULL CHECK (status IN ('PROCESSING', 'COMPLETED', 'FAILED')),
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ensure a user doesn't upload multiple definitive statements for the same account in the same month.
CREATE UNIQUE INDEX idx_unique_account_statement_month ON ledger.statements(account_id, statement_month);

-- ==========================================
-- TABLE: transactions
-- Domain: The immutable financial ledger.
-- ==========================================
CREATE TABLE ledger.transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES ledger.accounts(account_id) ON DELETE CASCADE,
    statement_id UUID REFERENCES ledger.statements(statement_id) ON DELETE SET NULL,
    parent_transaction_id UUID REFERENCES ledger.transactions(transaction_id) ON DELETE CASCADE, -- For split transactions
    external_tx_id VARCHAR(255), 
    amount DECIMAL(15, 2) NOT NULL CHECK (amount != 0),
    merchant VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    tags TEXT[], -- Multi-select tag array
    tx_date DATE NOT NULL,
    source VARCHAR(50) NOT NULL CHECK (source IN ('STATEMENT_UPLOAD', 'TELLER_SYNC', 'MANUAL_ENTRY')),
    type  VARCHAR(50) NOT NULL CHECK (type IN ('SALE', 'RETURN')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('PENDING_APPROVAL', 'POSTED', 'DELETED')),
    is_excluded BOOLEAN NOT NULL DEFAULT FALSE, -- Soft "delete" for synced/uploaded records
    is_manual BOOLEAN GENERATED ALWAYS AS (source = 'MANUAL_ENTRY') STORED, -- Strict UI control flag
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- QUERY OPTIMIZATION & RULES (transactions)
-- 1. Prevent duplicate records from automated Bank Syncs.
CREATE UNIQUE INDEX idx_unique_external_tx ON ledger.transactions(account_id, external_tx_id) WHERE external_tx_id IS NOT NULL;
-- 2. Optimize the main UI dashboard query (Fetch recent transactions for an account).
CREATE INDEX idx_tx_account_date ON ledger.transactions(account_id, tx_date DESC);
-- 3. Optimize Analytics pipeline queries (Fetch all posted transactions for a user across accounts).
CREATE INDEX idx_tx_status_date ON ledger.transactions(status, tx_date) WHERE status = 'POSTED';
-- 4. Optimize multi-select tag filtering from UI.
CREATE INDEX idx_tx_tags ON ledger.transactions USING GIN (tags);

-- ==========================================
-- TABLE: budgets & budget_lines
-- Domain: Time-series tracking of user spending limits.
-- ==========================================
CREATE TABLE ledger.budgets (
    budget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    effective_month DATE NOT NULL, -- Always stored as the 1st of the month (e.g., '2026-04-01')
    version INT DEFAULT 1, -- Incremented if user changes budget mid-month
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, effective_month, version) -- Ensures historical integrity
);

CREATE TABLE ledger.budget_lines (
    line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES ledger.budgets(budget_id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    limit_amount DECIMAL(15, 2) NOT NULL CHECK (limit_amount >= 0),
    UNIQUE (budget_id, category)
);

-- ==========================================
-- TABLE: upcoming_bills
-- Domain: Scheduled manual/recurring expenses for Dashboard view.
-- ==========================================
CREATE TABLE ledger.upcoming_bills (
    bill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    due_date_day INT NOT NULL CHECK (due_date_day BETWEEN 1 AND 31),
    category VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_upcoming_bills_user ON ledger.upcoming_bills(user_id) WHERE status = 'ACTIVE';

-- ==========================================
-- TABLE: bill_payments
-- Domain: Tracks the months for which a recurring bill was marked as paid.
-- ==========================================
CREATE TABLE ledger.bill_payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id UUID NOT NULL REFERENCES ledger.upcoming_bills(bill_id) ON DELETE CASCADE,
    paid_for_month DATE NOT NULL, -- The 1st of the month the bill applies to (e.g. '2026-03-01')
    transaction_id UUID REFERENCES ledger.transactions(transaction_id) ON DELETE SET NULL, -- Optional link to real transaction
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (bill_id, paid_for_month) -- Ensures a valid recurring bill cannot be paid twice for the same month
);