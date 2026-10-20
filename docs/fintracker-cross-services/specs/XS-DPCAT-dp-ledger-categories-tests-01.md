=========================
F2P TESTS (25)
=========================

--- CategoryCodeMigrationIT (7) ---
1. every SYSTEM category has a code derived from its name: DP-LEDGER-CATEGORIES-01 code backfill.
2. a SYSTEM category's code cannot be changed after creation: DP-LEDGER-CATEGORIES-01 immutable code.
3. a SYSTEM category's name stays editable while its code is unchanged: DP-LEDGER-CATEGORIES-01 editable name.
4. a USER category cannot carry a code: DP-LEDGER-CATEGORIES-01 code empty for USER.
5. re-running the SYSTEM category seed creates no duplicates and keeps every UUID: DP-LEDGER-CATEGORIES-01 seed upsert by code.
6. the repository exposes code and isActive, and food-and-drink displays as "Food & Drink": DP-LEDGER-CATEGORIES-01 / 02.
7. upgrading an existing database keeps the others/dining UUIDs and renames their transaction text: DP-LEDGER-CATEGORIES-01 uncategorized fallback.

--- TransactionServiceTest (1) ---
8. recategorizing a transaction persists "Food & Drink": DP-LEDGER-CATEGORIES-01 renames.

--- JooqStatementRepositoryIT (1) ---
9. the internal owner lookup works on a pooled connection that already served a user request: REQ-DP-05.

--- CategoryServiceTest (5) ---
10. re-creating a deactivated category reactivates it, keeping its UUID: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
11. deleting an unused custom category deactivates it: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
12. deleting an in-use category without a reassignment target deactivates it: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
13. deleting with a reassignment target reassigns transactions, then deactivates: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
14. the uncategorized SYSTEM category can never be deactivated: DP-LEDGER-CATEGORIES-01 uncategorized fallback.

--- CategoryControllerIT (2) ---
15. deleting an in-use category leaves the list while its transaction still references it: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
16. re-creating a deactivated category's name brings back the same category: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.

--- JooqCategoryRepositoryIT (3) ---
17. the migration seed includes uncategorized instead of others: DP-LEDGER-CATEGORIES-01 uncategorized fallback.
18. a deactivated category leaves the list and name/cap checks but stays findable by id: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.
19. reactivate brings a category back under the same id: DP-LEDGER-CATEGORIES-02 deactivate instead of delete.

--- InternalCategoryControllerIT (5) ---
20. GET /system returns every SYSTEM category with its code, display name and active flag: DP-LEDGER-CATEGORIES-02 system read API.
21. GET /system answers 304 when If-None-Match carries the current ETag: DP-LEDGER-CATEGORIES-02 ETag.
22. GET /users/{userId} returns only that user's categories, including deactivated ones: DP-LEDGER-CATEGORIES-02 user read API.
23. GET /users/{userId} answers 404 when the path user is not the caller's user: DP-LEDGER-CATEGORIES-02 user read API / invariant 5.
24. internal category endpoints reject a caller that is not allow-listed with 401: DP-LEDGER-CATEGORIES-02 internal-only.

--- InternalCallerFilterTest (1) ---
25. the internal caller filter guards the internal category routes: DP-LEDGER-CATEGORIES-02 internal-only.
