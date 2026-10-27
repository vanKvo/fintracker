=========================
F2P TESTS (38)
=========================

--- document-service · test_download_service (14) ---
1. owner gets a link for a clean file: DS-DL-01 Happy.
2. link expires in at most fifteen minutes: DS-DL-01 Requirement.
3. granted download writes an audit record: DS-DL-01 Requirement.
4. unknown document is not found and audited: DS-DL-01 Fail (404).
5. another user's document is indistinguishable from unknown: DS-DL-01 Fail (404, same for both).
6. file still in quarantine gets no link: DS-DL-01 Fail (409).
7. file that failed its scan gets no link: DS-DL-01 Fail (409).
8. clean file without a storage key gets no link: DS-DL-01 Fail (409).
9. no link is returned when the audit record cannot be written: DS-DL-01 Requirement (audit each download).
10. lookup failure is service unavailable: DS-DL-01 Requirement.
11. overlong document id is truncated in the audit record: DS-DL-01 Requirement (audit).
12. link lifetime of zero is rejected: DS-DL-01 Requirement (15 minutes at most).
13. negative link lifetime is rejected: DS-DL-01 Requirement (15 minutes at most).
14. link lifetime over fifteen minutes is rejected: DS-DL-01 Requirement (15 minutes at most).

--- document-service · test_signer (7) ---
15. link points at the clean bucket and key: DS-DL-01 Happy.
16. link lifetime is the requested expiry: DS-DL-01 Requirement.
17. link is served with no-store cache control: DS-DL-01 Requirement.
18. link downloads as an attachment with the original name: DS-DL-01 Happy.
19. file name cannot break out of the header: DS-DL-01 Requirement (safe link).
20. non-ascii file name gets an encoded name: DS-DL-01 Happy.
21. blank file name falls back to a generic name: DS-DL-01 Happy.

--- document-service · test_router (9) ---
22. owner gets the link with no-store headers: DS-DL-01 Happy.
23. user comes only from the authorizer context: DS-DL-01 Design Principle 2.
24. request without an authorizer context is unauthorized: DS-DL-01 Design Principle 2.
25. request with an invalid user id is unauthorized: DS-DL-01 Design Principle 2.
26. request with an empty user id is unauthorized: DS-DL-01 Design Principle 2.
27. unknown document is a 404 problem: DS-DL-01 Fail (404).
28. missing path parameter is a 404: DS-DL-01 Fail (404).
29. file in quarantine is a 409 problem: DS-DL-01 Fail (409).
30. unexpected failure is a 500 that hides the exception text: DS-DL-01 Requirement (error safety).

--- document-service · test_error_codes (1) ---
31. codes are unique and snake case: DS-DL-01 Fail (error catalog rule).

--- document-service · test_dynamodb_download_adapters (7) ---
32. owner finds the file: DS-DL-01 Happy.
33. another user's lookup misses: DS-DL-01 Fail (404).
34. unknown document misses: DS-DL-01 Fail (404).
35. unrecognised scan status is treated as not cleared: DS-DL-01 Fail (409).
36. audit record is stored under the caller's partition: DS-DL-01 Requirement (audit).
37. two audit records in the same instant do not collide: DS-DL-01 Requirement (audit).
38. storage failures become dependency errors: DS-DL-01 Requirement.
