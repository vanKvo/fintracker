# FinTracker Analytics - Financial Summary

## 1: AI-Generated Financial Summary

### Problem
Users see dashboards full of numbers and charts but can't easily tell what changed, why, or whether it's good or bad. Turning charts into conclusions takes effort, so most users look and then do nothing

### Why AI
Turning a user's own figures into a clear takeaways, personalized to them, adds values. The system calculates all the numbers itself; the AI only explains them.

### Requested Changes

1. User interface
Financial summary period dropdown: This month, Last month, Last 3 months, Year to date, Last 12 months.

2. userId parameter provided through auth session
No userId parameter is provided by LLM in MCP tools. userId is retrieved from auth session using context.

3. Structured output schema
LLM for interpretation only, arithmetic calculations from the code. The LLM never does arithmetic. It only get facts payload by invoking MCP tools. Structured JSON output is required.

4. Facts Payload
Facts payload (computed by your code):
- Income, total expenses and net cash flow, each with the change vs. the previous period
- Savings rate = (income − expenses) / income
- Top 3 categories by spend, and the biggest category increases and decreases vs. the previous period
- Unusual transactions (e.g., more than 2× a merchant's or category's typical amount) and new merchants
- Recurring charges: new subscriptions, price increases, total recurring per month
- Upcoming known bills in the next 14–30 days
- Emergency fund months of coverage and its status
- Budget vs. actual by category, if you have budgets

5. Let UI render numbers (predictable result)
- Any numbers or metrics should be displayed from fact payload by the frontend. The model only write comments and its interpretations

6. Limit the scope of advice
Recommendations are budgeting behaviors only, with no investment, tax or credit advice. Back this with a post-generation check for banned terms (e.g., "invest in", "stock", "guaranteed", "refinance") and show a short "informational only" note in the UI.

### Technical Details

1. Output Schema for Financial Summary 
{
  "headline": "string, max 120 chars",
  "overall_status": "on_track | watch | needs_attention",
  "highlights": [
    { "metric_id": "net_cash_flow | savings_rate | total_expenses | ...",
      "commentary": "string, max 160 chars" }
  ],
  "insights": [
    { "type": "spending_change | anomaly | subscription | income_change | emergency_fund | budget",
      "severity": "info | positive | warning",
      "title": "string, max 60 chars",
      "detail": "string, max 240 chars",
      "evidence": ["facts.category_changes[0]", "facts.recurring.new[1]"] }
  ],
  "recommendations": [
    { "action": "string, imperative, max 120 chars",
      "rationale": "string, max 200 chars",
      "estimated_monthly_impact": "number | null",
      "related_insight_index": "integer" }
  ],
  "data_caveats": ["string"]
}



