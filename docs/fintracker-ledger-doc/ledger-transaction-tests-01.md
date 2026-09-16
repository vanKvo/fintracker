=========================
F2P TESTS (61)
=========================

--- CategoryServiceTest (30) ---
1. a name containing characters outside alphanumeric/space is rejected: #3 Normalization — character validation.
2. a name is normalized to lowercase with a single underscore between words before storing: #3 Normalization.
3. a name that normalizes to blank (spaces only) is rejected: #3/#9 — blank name after normalization.
4. a category name longer than 100 characters is rejected: #9 Constraints — max length.
5. a category name of exactly 100 characters is accepted: #9 Constraints — max length boundary.
6. a name colliding with an existing SYSTEM-level category is rejected: #5 Name collisions.
7. a name colliding with the user's own existing custom category is rejected: #5 Name collisions.
8. the same normalized name is allowed for two different users: #2 User-level Category Isolation.
9. creation is rejected once the user already has 50 custom categories: #9 Constraints — cap.
10. the 50th custom category is accepted: #9 Constraints — cap boundary, not one past it.
11. the created category carries a generated categoryId and USER level: #1 Customizing categories.
12. updating a category not owned by the caller fails as not-found: #2 User-level Category Isolation (modify).
13. updating a SYSTEM-level category is rejected as immutable: #2 User-level Category Isolation (modify).
14. character validation is re-applied on rename: #3 Normalization.
15. a rename colliding with a different existing category is rejected: #5 Name collisions.
16. renaming a category to its own current name is not a self-collision: #5 Name collisions edge case.
17. rename preserves categoryId, changing only categoryName: #7 Updating/Renaming an existing custom category.
18. deleting a category not owned by the caller fails as not-found: #2 User-level Category Isolation (modify).
19. deleting a SYSTEM-level category is rejected as immutable: #2 User-level Category Isolation (modify).
20. deleting an unused custom category succeeds without a reassignment target: #6 Deleting an existing custom category.
21. deleting a category with referencing transactions and no reassignment target is rejected, carrying the referencing count: #6 Deleting an existing custom category.
22. deleting with a valid reassignment target reassigns transactions, then deletes: #6 Deleting an existing custom category.
23. a reassignment target equal to the category being deleted is rejected: #6 Deleting an existing custom category.
24. a reassignment target not visible to the user is rejected: #6 Deleting an existing custom category.
25. getAllCategoriesForUser merges SYSTEM and the caller's USER categories into one list: #1 Customizing categories.
26. with no custom categories, only system-level categories are returned: #1 Customizing categories.
27. another user's custom categories never appear in this user's list: #2 User-level Category Isolation.
28. the combined list is sorted alphabetically by display name, not by stored form: #4 Display of categories.
29. countTransactionsUsingCategory delegates to TransactionRepository, scoped to the requesting user: #6 Deleting an existing custom category (usage check).
30. checking usage of a category not accessible to the caller fails as not-found: #2 User-level Category Isolation.

--- CategoryControllerTest (7) ---
31. POST / creates a custom category and answers 201 with the display-formatted name: #1 Customizing categories.
32. GET / answers 200 with the combined system+custom list, display-formatted: #1/#4.
33. PUT /{categoryId} renames a category and answers 200: #7 Updating/Renaming an existing custom category.
34. DELETE /{categoryId} with no referencing transactions answers 204: #6 Deleting an existing custom category.
35. DELETE /{categoryId} with a reassignment target passes it through to the service: #6 Deleting an existing custom category.
36. GET /{categoryId}/usage answers 200 with the referencing transaction count: #6 Deleting an existing custom category (usage check).
37. every route is attributed to the request-attribute userId, never a body field: #2 User-level Category Isolation.

--- CategoryControllerIT (12) ---
38. invalid characters in a category name respond 400 application/problem+json: Error Handling row a.
39. a colliding category name responds 409: Error Handling row b.
40. updating a nonexistent categoryId responds 404: Error Handling row c.
41. updating another user's category responds 404, identically to nonexistent: Error Handling row c.
42. updating a SYSTEM-level category responds 400: Error Handling row d.
43. deleting a SYSTEM-level category responds 400: Error Handling row d.
44. deleting a category in use without a reassignment target responds 409 with the referencing transaction count: Error Handling row e.
45. a reassignment target that is the category being deleted responds 400: Error Handling row f.
46. creating a 51st custom category responds 400 stating the cap: Error Handling row g.
47. a category name that normalizes to blank responds 400: Error Handling row h.
48. an error response never leaks a stack trace or exception class name: RFC 9457 Problem Details.
49. a successful create/list/update/delete round-trip through real HTTP: #1/#4/#6/#7 end to end.

--- JooqCategoryRepositoryIT (9) ---
50. exactly 17 SYSTEM-level categories exist, including groceries and others: migration seed data.
51. unique index rejects a duplicate (user_id, category_name) for USER-level rows: #5 Name collisions.
52. the same normalized name is permitted for two different users at the DB level: #2 User-level Category Isolation.
53. a USER-level category is invisible to another user: #2 User-level Category Isolation.
54. a SYSTEM-level category is accessible to every user: #1 Customizing categories.
55. countByUserId counts only that user's own custom categories, not SYSTEM rows: #9 Constraints — cap.
56. renaming via update() preserves categoryId, changing only category_name: #7 Updating/Renaming an existing custom category.
57. ON DELETE RESTRICT prevents deleting a category referenced by a transaction directly at the database level: #6 Deleting an existing custom category.
58. deleting a category with no referencing transactions succeeds: #6 Deleting an existing custom category.

--- TransactionCategoryLinkIT (3) ---
59. transactions.category_id is a real foreign key; inserting a transaction against a nonexistent categoryId is rejected by the database: #7 Updating/Renaming an existing custom category.
60. renaming a category is immediately visible on a transaction created before the rename, without rewriting the transaction row: #7 Updating/Renaming an existing custom category.
61. reassignCategory moves every referencing transaction to the new category and leaves other transactions untouched: #6 Deleting an existing custom category.
