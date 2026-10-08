# Bug name: Unknown merchants permanently cached as Uncategorized

## Problem
Every merchant that did not match the built-in regex list was imported as "Uncategorized", and stayed that way on every later import. The shared MerchantRegistry cache only ever filled up with "Uncategorized" entries. Unit tests exercising this path also made a real Comprehend API call with the developer's AWS credentials.

### Root cause:
- The Comprehend endpoint ARN had a literal `*` in place of the account ID, so every `ClassifyDocument` call failed validation. The endpoint was never provisioned either.
- The failure was caught and turned into `("Uncategorized", "General", 0.0)`, which `categorize_merchant` then wrote to the MerchantRegistry. The next import hit that cache entry before reaching the classifier, so the merchant could never be categorized again.

### Code with bug:
```python
# src/categorizer/service.py
response = _comprehend.classify_document(
    Text=f"Purchase at: {merchant}",
    EndpointArn=f"arn:aws:comprehend:us-east-1:*:document-classifier-endpoint/fintracker-merchant-classifier",
)
...
except Exception as e:
    logger.warning("Comprehend categorization failed", error=str(e))
return "Uncategorized", "General", Decimal("0.0")

...
category, sub_category, confidence = _comprehend_categorize(merchant)
cache_merchant(merchant, category, sub_category, confidence)  # caches the failure
```

## Solution
Fixed as part of REQ-DP-09 (`docs/fintracker-data-pipelines/data-pipeline-spec-02.md`), which removes Comprehend and the shared cache entirely instead of repairing them. An idle Comprehend endpoint would cost about $1,300/month.

1. Removed the Comprehend client and `categorizer/repository.py` (MerchantRegistry lookups and writes).
2. Categorization is now: bank-provided category (CSV) → regex list → "Uncategorized". Nothing is cached, so an Uncategorized result can be fixed later by the user's own merchant rule (Ledger, later phase).
3. Removed the MerchantRegistry table and the Comprehend/MerchantRegistry IAM statements from dev Terraform.

### Fixed Code
```python
# src/categorizer/service.py
def categorize_merchant(merchant: str, bank_category: Optional[str] = None) -> MerchantCategory:
    translated = translate_bank_category(bank_category)
    if translated:
        return MerchantCategory(category=translated, sub_category="General", source="BANK")

    result = _regex_categorize(merchant)
    if result:
        return MerchantCategory(category=result[0], sub_category=result[1], source="REGEX")

    return MerchantCategory(category=UNCATEGORIZED, sub_category="General", source="NONE")
```
