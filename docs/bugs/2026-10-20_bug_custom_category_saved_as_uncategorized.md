# Bug name: Recategorizing a transaction to a custom category saves it as Uncategorized

## Problem
In the Transactions page, a user picks one of their own categories (for example "Gifts") for a transaction. The change saves without an error, but the transaction then shows **Uncategorized** (before DP-LEDGER-CATEGORIES-01 renamed it, **Others**). Only the 17 built-in categories could be chosen. Splitting a transaction into a custom category did the same.

The stored `category_id` was also never changed by a recategorize, so it kept pointing at the old category while the text changed.

### Root cause:
The category edit and the split path resolved the requested name against the hard-coded `TransactionCategory` enum (the 17 SYSTEM labels), not against the `ledger.categories` table. `TransactionCategory.resolve()` maps anything it doesn't know to its fallback, so every custom category name became Uncategorized. The repository update only wrote the text column. The drop-down list (`GET /transactions/categories`) came from the same enum, so custom categories were never offered either.

### Code with bug:
```java
// TransactionServiceImpl
@Override
public void updateCategory(UUID transactionId, String category, UUID userId) {
    transactionRepository.findByIdAndUserId(transactionId, userId)
            .orElseThrow(() -> new TransactionNotFoundException(transactionId));
    transactionRepository.updateCategory(transactionId, TransactionCategory.resolve(category).label());
}

private Transaction buildChildTransaction(Transaction parent, SplitRequest split) {
    return new Transaction(
            null, parent.accountId(), parent.statementId(), parent.transactionId(),
            null, split.amount(), parent.merchant(), TransactionCategory.resolve(split.category()).label(),
            ...);
}

// TransactionController
@GetMapping("/categories")
public ResponseEntity<List<String>> getCategories() {
    return ResponseEntity.ok(TransactionCategory.LABELS);
}

// JooqTransactionRepository: only the text column changes
public void updateCategory(UUID transactionId, String category) {
    dsl.update(table(name(SCHEMA, TX_TABLE)))
            .set(field("category"), category)
            .where(field("transaction_id").eq(transactionId))
            .execute();
}
```

## Solution
Categories are resolved against the database. Every recategorize changes the id and the text together.

1. `PATCH /transactions/{id}` accepts `categoryId`. The category must be one of the user's own categories or a SYSTEM one, and active:
   - another user's category answers 404, like a missing one;
   - an inactive category answers 400.
2. A `category` name is still accepted. It is resolved by normalized name among the user's active categories, with the user's own taking precedence over SYSTEM. An unknown name is now a 400 instead of being saved silently as Uncategorized.
3. Split children are resolved the same way and carry the `categoryId`.
4. `GET /transactions/categories` lists the display names of the user's active categories (custom and SYSTEM) from the database.
5. The repository writes `category_id` and `category` in one update.
6. `TransactionCategory` is no longer used by any production code.

Regression tests: `TransactionRecategorizeIT` (custom category by id and by name, SYSTEM category, another user's category, inactive category, unknown name, picker list, split children) and `TransactionServiceTest.UpdateCategory`.

### Fixed Code
```java
// TransactionServiceImpl
@Override
public void updateCategory(UUID transactionId, String category, UUID userId) {
    transactionRepository.findByIdAndUserId(transactionId, userId)
            .orElseThrow(() -> new TransactionNotFoundException(transactionId));
    store(transactionId, categoryResolver.requireAssignableByName(category, userId));
}

@Override
public void recategorize(UUID transactionId, UUID categoryId, UUID userId) {
    transactionRepository.findByIdAndUserId(transactionId, userId)
            .orElseThrow(() -> new TransactionNotFoundException(transactionId));
    store(transactionId, categoryResolver.requireAssignable(categoryId, userId));
}

private void store(UUID transactionId, Category category) {
    transactionRepository.updateCategory(
            transactionId, category.categoryId(), CustomCategoryResponse.from(category).displayName());
}

// TransactionCategoryResolver
public Category requireAssignable(UUID categoryId, UUID userId) {
    var category = categoryRepository.findByIdAndAccessibleToUser(categoryId, userId)
            .orElseThrow(() -> new CategoryNotFoundException(categoryId));
    if (!category.isActive()) {
        throw new IllegalArgumentException("This category is no longer active. Choose another one.");
    }
    return category;
}

public Category requireAssignableByName(String displayName, UUID userId) {
    var normalized = displayName.trim().replaceAll("\\s+", "_").toLowerCase();
    return categoryRepository.findActiveByNormalizedNameAccessibleToUser(normalized, userId)
            .orElseThrow(() -> new IllegalArgumentException(
                    "Unknown category. Choose one of your active categories."));
}

// TransactionController
@GetMapping("/categories")
public ResponseEntity<List<String>> getCategories(@RequestAttribute("userId") UUID userId) {
    return ResponseEntity.ok(transactionService.assignableCategoryNames(userId));
}

// JooqTransactionRepository
public void updateCategory(UUID transactionId, UUID categoryId, String category) {
    dsl.update(table(name(SCHEMA, TX_TABLE)))
            .set(field("category_id"), categoryId)
            .set(field("category"), category)
            .where(field("transaction_id").eq(transactionId))
            .execute();
}
```
