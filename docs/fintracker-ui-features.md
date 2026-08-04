You’re are a senior UI/UX Frontend Developer and Backend Developer. Here are the two comprehensive documents outlining the FinTracker frontend architecture and UI logic.
Project: FinTracker (Cloud-Native Personal Finance SaaS). Global State & Settings: English is the default and only supported language. All dates and currencies should respect user-defined formatting from settings.
# 1. Dashboard View
## Purpose: 
The central operational hub providing a 3-second overview of financial health.
## Features:
- Financial Overview Cards: Total Balance, Monthly Income, Monthly Expenses, Current Month Cash Flow, Net Savings.
- "Safe to Spend" Metric: A highly prominent, mathematically calculated number showing disposable income remaining after fixed bills, pending transactions, and savings goals.
- Action Hub: A dedicated alert center replacing "Needs Attention." Flags disconnected bank accounts, unreviewed transactions, or over-budget categories.
- Upcoming Bills: A chronological list of upcoming fixed expenses. Data Source: Driven by a user-defined manual/scheduled CRUD table.
- Pending Transactions Section: A quick-view list of uncleared transactions awaiting settlement or approval.
- Spending Insights:
    Line Graph: Total actual spending vs. total budget limits for the current year.
- Over-budget warnings: Visual highlights for specific categories exceeding their monthly limit.
# 2. Transactions View
## Purpose: 
The primary ledger and data integrity center.
## Features:
- Search & Filter Engine: A multi-select filter bar supporting merchant text search, date ranges, categories, accounts, tags, and transaction status (cleared/pending).
- Data Table & Aggregation: Displays rows of transactions with a dynamic "Total Amount" calculation for the current filtered view.
- Row-Level Actions:
    - Edit Category.
    - Add Tag.
    - Split Transaction (Divide one imported row into multiple sub-transactions for accurate categorization).
    - Mark as Approved.
    - Exclude: A toggle to hide a transaction from budget and report calculations without deleting the immutable database record.
    - Delete: Strictly restricted. The delete button is only active/visible if the transaction's is_manual flag is true.
- Bulk Actions: Checkbox selection to Approve, Exclude, Export to CSV, or Add a Tag to multiple rows simultaneously.
- Manual Entry: A prominent "Add Transaction" floating action button for cash entries.
# 3. Statements View
## Purpose: 
A secure, immutable document vault.
## Features:
- Upload Statement: A drag-and-drop zone with encapsulated file validation (verifying file extensions, size limits, and utilizing magic byte sniffing to guarantee the upload is a legitimate PDF, CSV, or standard image format).
- Statement Table: Columns for Date Range, Account Name, Total Transactions, Pending Count, Approved Count, Status (Complete/Processing), and Actions.
- Row-Level Actions:
    - View Transactions: Redirects to the Transactions tab, automatically applying the date range and account filters for this specific statement.
    - Download Statement: Fetches the raw file.
    - Approve All Pending.
    Delete: Hard deletes the statement file and cascades the deletion to all associated transactions in the database.
- Visual Completeness Tracking: A visual grid/calendar. Green checkmarks indicate reconciled/saved months; red dots indicate missing statements. Auto-synced accounts (Basic/Pro plan) display a "Bank Provided" icon.
## 4. Budgets View
## Purpose: 
Proactive, month-to-month financial planning.
## Features:
- Time Navigation: Month-Year filter. Rule: Past months are strictly read-only to preserve historical data integrity.
- Visual Pacing Indicators: Category progress bars utilizing color psychology (Green = Good, Yellow = Nearing Limit, Red = Over Limit), contextualized by the current day of the month.
- Create Budget Engine: * Defaults to the current month.
    - If no budget exists, the UI automatically loads a "Base Template" mirroring all categories and limits from the previous month.
    - Users can add/remove categories and edit limits for the current and future months.
# 5. Reports View
## Purpose: 
Deep-dive analytics and historical visualizations.
## Features:
- Time Range Filter: Segment by This Month, Last Month, Last 3 Months, This Year.
- Period Summary: Top-level metrics (Total Income, Total Expenses, Net Savings).
- Visual Charts:
    - Spending Category (Pie Chart) with Interactive Drill-Downs: Clicking a pie slice opens a slide-out panel detailing the specific transactions comprising that slice.
    - Cash Flow Trend & Spending Trend (Line Graphs).
    - Year-over-Year / Month-over-Month Comparisons.
- Emergency Fund Calculator: An interactive widget to calculate runway based on average monthly expenses.
- AI Insights Section: Powered by backend LLM analysis (e.g., via AWS Bedrock), displaying:
    - Subscription Creep Detection: Flags hidden price increases in recurring services.
    - Anomaly Alerts: Highlights unusual spending spikes compared to historical averages.
- Export: One-click CSV and PDF generation.
# 6. Settings View
## Purpose: 
User preferences, security, and external integrations.
## Features:
- Profile: First Name, Last Name, Email, Phone Number.
- Subscription Management: Upgrade/Downgrade paths.
- Preferences: Currency selection (Language selection is omitted; English is default).
- Notifications: Toggles for Email updates, SMS alerts (for anomalies/large transactions), and Marketing.
- Security: Two-Factor Authentication (2FA) setup.
- Bank Connections (Gated to Basic/Pro): 
    - Connection Health Dashboard showing active APIs (Teller, etc.) and uptime.
    - Real-Time Sync Status with "Last updated" timestamps and a manual "Refresh All" trigger.
    - Graceful Error Handling: Intercepts broken API connections or MFA prompts and renders an immediate "Update Credentials" UI flow.