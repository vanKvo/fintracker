# FinTracker Analytics Spec 01

## REQ-FA-01: Budget variance explanations with history 

### Problem
User asks: "Why am I $400 over budget this month?"

Why structured tools aren't enough: get_budget_status and get_spending_by_category can show where the overspend is. They can't say whether it's normal for this user. The context is in past explanations: "This is your annual car insurance renewal. It also hit last March, and you marked it as expected."

### Requested Changes
Pipeline:

Each monthly summary and insight the system generates is stored along with the user's feedback (helpful, dismissed, "this is expected").
Those summaries are embedded, so the corpus grows per user every month. That growth is what justifies retrieval over stuffing everything into the prompt.
At query time the agent gets the current numbers from the SQL tools and the similar past months from the retriever, then generates the explanation.
Why it's the best first build:

It's a direct match for the resume wording: "natural-language financial summaries" and "explanations of budget variances."
It uses data the system generates itself, so it's less sensitive than bank statements.
It needs no new ingestion source.

## REQ-FA-02: Semantic spending-pattern search
### Problem
User asks: "How much have I spent on my kids' activities this year?"

Why SQL can't answer: no category says "kids' activities." The spending is scattered across a swim school, a sports store, an LEGO order and a summer camp, and a LIKE match won't connect them.

### Requested Changes
Pipeline:

Embed each transaction's merchant, description and tags (the Ledger model already has description and tags).
Retrieve semantically matching transactions for the user.
Pass the matched IDs to structured aggregation so the dollar total comes from SQL, not from the model's arithmetic.
Answer: "$2,340 across 14 transactions, mostly swim lessons and camp."