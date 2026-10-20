# FinTracker Data Pipeline Spec 02

## REQ-DP-09: Updating Categories Workflow
### Problem
The Normalizer calls a Comprehend custom classifier endpoint, which is billed per hour while it exists, whether or not you use it: about $1.80/hour, roughly $1,300/month. A custom classifier needs labeled training data and costs about $3/hour to train and about $0.50/month to store, on top of the always-on endpoint charge. This creates a surprise large bill unnecessarily. 

### Requested Changes
We will remove Comprehend from categorizing logic. For CSV documents, we use bank-provided category. For PDF statements, where categories are not provided, we will use this flow: regex → merchant cache → ask user to map categories for uncategorized one. 

1. Per-user rule in Ledger
New Ledger table of merchant→category rules per user, protected by the same per-user row security as categories and linked to them (so user-defined categories work). Pipeline stops using the global DynamoDB MerchantRegistry. That table + IAM are removed. Regex stays as the only shared default.

A user's own rule for a merchant takes priority over both the bank's category and the built-in list.

2. Remember user-picked catetory by default, opt-out 
A 'Always use this for < merchant>' checkbox, checked by default. Creates/updates the rule and also fills in the user's other pending uncategorized transactions from that merchant. Unchecking makes it a one-off (e.g. a Target trip that was really for a gift).

Delivery is phased: Phase 1 (this section's Data Pipeline changes) removes Comprehend and adds bank categories; the per-user rules (items 1–2) land in the Ledger and UI in later phases.

3. Bank Category First, Known-Merchant List Second,  Uncategorized Last
When a bank's export includes its own category for a transaction (e.g. Chase and Discover credit card downloads), the system uses it, translated into FinTracker's category names (e.g. the bank's "Food & Drink" becomes Dining, "Bills & Utilities" becomes Utilities). The bank's category column is used whenever the file has one; the user does not have to confirm it in the column-mapping dialog.

When the bank gives no category, or gives one FinTracker has no translation for, the system checks a built-in list of well-known merchants (e.g. Uber is Transportation, Netflix is Subscriptions). A transaction that matches neither is marked Uncategorized rather than guessed, and is left for the user to categorize.

4. No Shared Learning
The pipeline no longer remembers categories in a store shared by all users. One user's categorization never changes how another user's transactions are categorized.

5. Missing or Unrecognized Bank Category
Reading the bank's category must never make an import fail: a missing, blank, or unrecognized bank category will be categorized as "Uncategorized".

6. Use Categories matched Categories in Ledger
Categories produced by the pipeline must be names the Ledger already recognizes, so imported transactions don't collapse into "Others".

### Data Impacts:
- The shared merchant cache table (MerchantRegistry) and its access permissions are removed from the pipeline's infrastructure.
- The Comprehend permission is removed from the Normalizer's role.
- A raw CSV transaction gains an optional bank-provided category.
- Chase's baseline column mapping names its real category column ("Category"); it previously pointed at the transaction-type column ("Type").
- No Ledger schema change in this phase.

### Pipeline Stage Mapping:
Location: `services/fintracker-data-pipeline/src/`
- `extractor/service.py::parse_csv_transactions` — reads a `Category` column (case-insensitive header match) into `RawTransaction.raw_category`.
- `categorizer/bank_categories.py` (new) — bank category label → FinTracker category label.
- `categorizer/service.py::categorize_merchant` — bank category → regex → Uncategorized; Comprehend client and MerchantRegistry lookups/writes removed.
- `normalizer/service.py::normalize_and_categorize` — passes each row's bank category to the categorizer.
- `categorizer/repository.py` — deleted.
- `infrastructure/terraform/environments/dev/` — MerchantRegistry table, `MERCHANT_REGISTRY_TABLE` env var, and the `comprehend:ClassifyDocument` / MerchantRegistry IAM statements removed.

### Interface Details:
```python
def categorize_merchant(merchant: str, bank_category: Optional[str] = None) -> MerchantCategory:
    """bank category (translated) -> regex -> "Uncategorized".
    MerchantCategory.source is "BANK", "REGEX", or "NONE".
    """

def translate_bank_category(bank_category: Optional[str]) -> Optional[str]:
    """Case/whitespace-insensitive lookup; None when blank or unknown."""
```
- `RawTransaction.raw_category: Optional[str] = None`
- Category labels emitted: the Ledger's `TransactionCategory` labels (Groceries, Dining, Transportation, Shopping, Entertainment, Utilities, Housing, Healthcare, Insurance, Subscriptions, Travel, Education, Personal Care, Income, Transfer, Fees, Others) plus `Uncategorized`.
- Ledger push payload is unchanged (`category`, `subCategory`).

F. Error Handling:
- Unrecognized or blank bank category: not an error; falls through to the built-in merchant list, then Uncategorized.
- CSV without a category column: not an error; every row's bank category is empty.
