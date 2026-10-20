# Transactions (TS) 

## REQ-TS-01: Customizing categories
### Problem:
For adding a transaction, the existing category selection only has a limited number of categories. The user cannot create their own custom category as needed, e.g., auto property tax.

### Requested Changes:
1. Customizing categories
The system shall allow the user to create their own categories. Besides the existing system-level categories, which is always available for the user, the system will display any existing categories that are created by the user. If there're no existing custom categories, the system display system-level categories only. 

2. User-level Category Isolation
The user-level category is linked to that user only and is only shown to that user. All users can see system-level categories, but not user-level categories.

The user can only update or delete their own custom categories, and attempting to alter another user's category or any system-level category must fail. All modifications requires to check if a custom category belongs to the user before modification can occur.

3. Normalization of user-level category
The user can only input their categories using alphanumeric and space only. If the user types any characters outside of that set, the system shall not allow the user to create or update the category and shall let the user know allowable characters in the category name. All categories are manually entered by the user should be stored in the database with criteria below:
- stored as lowercase letters.
- all extra spaces between words are removed and only one space is allowed; the space is replaced with underscore.

The consistency of the user-level category format will help group expenses or income based on category for transactions.

4. Display of categories.
When displaying the user-level categories to the user, the system shall replace underscores with spaces and display in Title Case format.

Both custom categories and and system-level categories are added in the same selection list and ordered by alphabet.

5. Name collisions
If the user creates a category that exists in the system-level category or collides with another existing custom category, the system shall show the user that the category exists and does not allow to create a new one, prompting the user to change the category name.

6. Deleting an existing custom category
If the user deletes a custom category that transactions currently reference, the system shall ask the user to reassign the custom category to another category before proceeding with deletion. The system shall display all existing categories, including system-level and user-level categories, that the user can choose for reassignment.

7. Updating/Renaming an existing custom category
If the user renames an category, the system shall immediately display new name for transactions referencing to it. The system shall reference categoryId, so we need to update the Transaction table to have the category column reference to categoryId instead of category name.

8. Updating Budget feature to use categoryId
Budget features such as budget_lines/budget_template_lines currently match transaction categories by string. The system should be updated to have Budget features match transaction categories by categoryId.

9. Constraints
Each user should have a maximum of 50 custom categories, not including the system-level categories. Category name max length is 100.

### Technical References:
#### Interface Details:
a. REST endpoint mappings
```
POST   /api/v1/ledger/categories                  -> CustomCategoryRequest -> CustomCategoryResponse (201)
GET    /api/v1/ledger/categories                   -> CustomCategoryResponse[] (200)
PUT    /api/v1/ledger/categories/{categoryId}      -> CustomCategoryRequest -> CustomCategoryResponse (200)
DELETE /api/v1/ledger/categories/{categoryId}      -> DeleteCategoryRequest (optional body) -> 204
GET    /api/v1/ledger/categories/{categoryId}/usage-> CategoryUsageResponse (200)
```

`GET /categories` returns the single combined, display-formatted, alphabetized list described in Requested Changes #1/#4 (system-level rows plus the caller's own user-level rows) — it is not just the user's custom categories, so the service layer needs a method that merges both sources, not only `getCustomCategories`.

`DELETE` supports Requested Changes #6 (reassignment-before-delete): when the category being deleted has referencing transactions, the request must carry a `reassignToCategoryId`, or the endpoint responds with the in-use error below instead of deleting anything. 

`GET .../usage` lets the client check up front whether a reassignment prompt is needed, without attempting the delete first.

b. These method signatures will be added to a new CategoryService:

```java
CustomCategory createCustomCategory(String category, UUID userId)
List<CustomCategory> getAllCategoriesForUser(UUID userId)   // merges SYSTEM + USER, display-formatted, sorted by alphabet
CustomCategory updateCustomCategory(UUID categoryId, String newName, UUID userId)
long countTransactionsUsingCategory(UUID categoryId, UUID userId)  // backs the usage-check endpoint
void deleteCustomCategory(UUID categoryId, UUID userId, UUID reassignToCategoryId)  // null when unused
```
`createCustomCategory`/`updateCustomCategory` are the enforcement points for Requested Changes #3 (character validation), #5 (collision check), and #8 (50-category cap per user) — all three are service-layer checks, not just DB constraints, since each needs a specific user-facing message.

c. Transaction create/update endpoints
`TransactionService`'s create/update signatures shall be updated to take `categoryId` instead of a category string. Because `transactions.category_id` becomes a foreign key (see Data Contracts).

#### Data Contracts:
a. DTO Objects
```java
CustomCategoryRequest(String categoryName)
CustomCategoryResponse(UUID categoryId, String displayName, String level)  // level: SYSTEM | USER
CategoryUsageResponse(long transactionCount)
```
`categoryName` in the request is the raw user input; the server applies Requested Changes #3's normalization before storing. `displayName` in the response is the Title Case, underscore-to-space form from Requested Changes #4 — derived at read time, not stored (see below). `level` lets the UI distinguish system rows (not editable/deletable) from the user's own rows in the merged list.

b. Tables
-- Categories table --
```sql
category_id    UUID PRIMARY KEY,
category_name  VARCHAR(50) NOT NULL,   -- normalized form: lowercase, single-underscore-separated
level          VARCHAR(6)  NOT NULL,   -- CHECK (level IN ('SYSTEM','USER'))
user_id        UUID NULL REFERENCES ledger.accounts... -- null for SYSTEM rows
```
`category_name` stores the normalized form produced by Requested Changes #3, not the display form. The Title Case/underscore-to-space transformation is applied only when rendering, so it doesn't need to be kept in sync with the stored value.

-- Uniqueness constraints --
A unique index on (user_id, category_name) for USER-level rows, and on category_name for SYSTEM-level rows. 

-- Transaction table update --
`ledger.transactions.category` (currently free-text `VARCHAR(100)`, resolved through the
`TransactionCategory` enum) is replaced with `category_id UUID NOT NULL REFERENCES
ledger.categories(category_id) ON DELETE RESTRICT`. `ON DELETE RESTRICT` backstops 

-- Migration & backfill --
A new migration must:
1. create the `categories` table
2. seed it with the 17 existing
`TransactionCategory` enum values (`GROCERIES`, `DINING`, ... `OTHERS`) as `SYSTEM`-level rows,
3. add `transactions.category_id`, backfill it by matching each row's existing `category` string (lowercase, using underscore instead of spaces) to the corresponding seeded row — falling back to `OTHERS`.


-- Budget feature update --
`ledger.budget_lines.category` and `ledger.budget_template_lines.category_name` are free-text strings matched case-insensitively against transaction categories today (`JooqBudgetRepository`). The system should be updated to have Budget features match transaction categories by categoryId.

#### Error Handling:
a. Category name contains characters outside alphanumeric/space: 400 — message states the allowed character set
b. Category name collides with a system or another custom category, post-normalization (#5): 409 — names the existing category so the UI can prompt for a different name 
c. `categoryId` not found, or belongs to another user (update/delete): 404 — same not-found response either way, so existence isn't leaked across tenants
d. Update/delete targets a SYSTEM-level category: 400 — system categories are read-only 
e. Delete targets a category with referencing transactions and no `reassignToCategoryId` given: 409 — includes the referencing transaction count so the UI knows a reassignment prompt is needed.
f. `reassignToCategoryId` does not exist, is the category being deleted, or is not visible to the user (not SYSTEM and not their own): 400
g. User already has 50 custom categories (#8): 400 — states the cap |
h. Normalized category name is blank (e.g. input was only spaces): 400 


