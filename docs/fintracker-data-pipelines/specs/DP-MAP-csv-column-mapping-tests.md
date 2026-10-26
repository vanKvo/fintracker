> **Tests for:** [DP-MAP-csv-column-mapping-spec.md](DP-MAP-csv-column-mapping-spec.md)

=========================
F2P TESTS (56)
=========================

--- TestHeaderSignature (6) ---
1. column order and letter case do not change the signature: DP-MAP-01 Happy.
2. the signature is the first 16 hex characters of the hash of the sorted joined headers: DP-MAP-01.
3. adding a column gives a new signature: DP-MAP-01 Alt.
4. whitespace is trimmed and collapsed: DP-MAP-01.
5. duplicate header names are rejected as an invalid CSV: DP-MAP-01 Fail.
6. the mapping hash ignores letter case and order but not which column is which field: DP-MAP-03.

--- TestChooseProposal (8) ---
7. the user's own mapping wins over the baseline and carries the baseline as a hint: DP-MAP-02 Happy.
8. no hint when the user's mapping matches the baseline: DP-MAP-02 Alt.
9. a user with no mapping gets the baseline for the signature: DP-MAP-02 Alt.
10. a stored header spelled differently resolves to the file's own spelling: DP-MAP-02.
11. the nearest baseline is used when two of three required fields overlap: DP-MAP-02.
12. the baseline with the most overlap is the nearest: DP-MAP-02.
13. one overlapping field is not enough, so the defaults apply: DP-MAP-02.
14. the defaults match the canonical names in any letter case: DP-MAP-02.

--- TestProposeColumnMapping (5) ---
15. a user who corrected the mapping last month gets their own proposed: DP-MAP-02 Happy.
16. another user's mapping never changes my proposal: DP-MAP-03 Happy / Principle 1.
17. every column is either mapped or listed unmapped: DP-ING-01 Mapping Transparency.
18. an unknown bank opens the dialog with the defaults and raises no format alarm: DP-MAP-04 Alt.
19. a table that cannot be read falls back to the defaults and the dialog still opens: DP-MAP-02 Fail.

--- TestBankFormatChange (3) ---
20. a new signature for a bank with a baseline is logged with the bank and signature only: DP-MAP-04 Happy.
21. a known signature raises nothing: DP-MAP-04.
22. a bank with no baseline at all raises nothing: DP-MAP-04 Alt.

--- TestRecordConfirmation (6) ---
23. the user's next upload proposes their correction and other users are unchanged: DP-MAP-03 Happy.
24. confirming the proposal unchanged still records a vote: DP-MAP-03 Alt.
25. a later vote from the same user replaces the earlier one: DP-MAP-03.
26. a confirmation never writes the baseline: DP-MAP-03 / Principle 1.
27. losing the save or the vote is logged and never raised: DP-MAP-03 Fail.
28. a confirmation with no stored proposal signature is skipped quietly: DP-MAP-03.

--- TestConfirmColumnMappingAgainstTheProposal (5) ---
29. confirming resumes first, then saves the user's mapping and vote: DP-MAP-03.
30. a failed save does not stop the import resuming: DP-MAP-03 Fail.
31. a mapping to a column the file does not have is refused and nothing resumes: DP-MAP-03.
32. two fields on the same column are refused: DP-MAP-03.
33. a bank id that is not the job's own is refused, so votes cannot be cast for another bank: DP-MAP-03 / Principle 3.

--- TestChangeShareMetric (3) ---
34. the share is published once there are at least five confirmations: DP-MAP-04.
35. with fewer than five confirmations the share is still published per bank: DP-MAP-04.
36. the alarm metric is 0 below five confirmations: DP-MAP-04.

--- TestPromotion (12) ---
37. three distinct users agreeing notify the owner once: DP-MAP-05 Happy.
38. a fourth confirmation does not notify again: DP-MAP-05 Happy.
39. one user confirming ten times counts as one vote and never qualifies: DP-MAP-05 Alt.
40. three votes for X and two for Y is only sixty percent and does not qualify: DP-MAP-05 Alt.
41. votes older than 30 days do not count: DP-MAP-05.
42. a mapping the baseline already holds is not announced: DP-MAP-05.
43. the thresholds are configuration values: DP-MAP-05 Open Questions.
44. without a topic the notice is skipped and logged, not raised: DP-MAP-05.
45. promoting adds a baseline the fourth user is proposed, recording who and when: DP-MAP-05 Happy.
46. a baseline holds no user ids: DP-MAP-06 Alt.
47. a promotion that would remove a required field is refused: DP-MAP-05 Fail.
48. promoting a mapping nobody proposed is refused: DP-MAP-05.

--- TestAccountDeletion (5) ---
49. after deletion no item with that user's id remains: DP-MAP-06 Happy.
50. a promoted baseline stays: DP-MAP-06 Alt.
51. it pages through every item of a user with many mappings: DP-MAP-06.
52. the handler accepts the EventBridge shape and the SQS-wrapped shape: DP-MAP-06.
53. an event without a user id deletes nothing and fails loudly: DP-MAP-06.

--- TestSeededBaseline (3) ---
54. every signature is the hash of that entry's headers: DP-MAP-01 / Appendix A.
55. every mapping points at columns the entry has: DP-MAP Appendix A.
56. no bank has the same signature twice: DP-MAP Appendix A.
