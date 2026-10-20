=========================
F2P TESTS (233)
=========================

--- test_clients.TestIamSignedCalls (3) ---
1. ledger call is SigV4 signed: FS-02 Alt, IAM-authenticated service calls.
2. budget call is SigV4 signed: FS-02 Alt, IAM-authenticated service calls.
~~3. user profile call is SigV4 signed: FS-02 Alt, IAM-authenticated service calls.~~ *Removed 2026-10-20: settings now arrive in the verified context (D23).*

--- test_tools (10) ---
4. no tool accepts a user id parameter: FS-02 tools use the same mechanism.
5. tool without bound user is refused: FS-02 tools use the same mechanism.
6. get dashboard overview combines overview and safe to spend: FS-02 tools use the same mechanism.
7. get spending by category delegates to reports repository: FS-02 tools use the same mechanism.
8. get monthly trend delegates to reports repository: FS-02 tools use the same mechanism.
9. detect spending anomalies returns only anomalies slice: FS-02 tools use the same mechanism.
10. detect subscription creep returns only creeps slice: FS-02 tools use the same mechanism.
11. list transactions delegates to ledger client with all filters: FS-02 tools use the same mechanism.
12. get budget status delegates to ledger client: FS-02 tools use the same mechanism.
13. get savings goal progress delegates to user profile client: FS-02 tools use the same mechanism.

--- test_identity (6) ---
14. reads internal user id from authorizer lambda context: FS-02.
15. missing or blank authorizer user id is none: FS-02.
16. local dev user id only when app env is local: FS-02 local-dev identity (Alt).
17. startup refuses local dev user id outside local: FS-02 local-dev identity (Alt).
18. startup allows local dev user id when local: FS-02 local-dev identity (Alt).
19. tool context has no user until bound: FS-02.

--- test_routes_auth (5) ---
20. dashboard uses authorizer user and ignores forged ids: FS-02.
21. dashboard without authorizer user is 401 problem: FS-02.
22. spending report uses authorizer user: FS-02.
23. monthly trend without authorizer user is 401: FS-02.
24. old insights endpoint is no longer served: FS-13 old insights endpoint removed.

--- test_router (8) ---
25. ai insights endpoint returns generate insights result: FS-02.
26. ai insights endpoint never leaks raw exception text: FS-02.
27. summary uses the authorizer user and default period: FS-02.
28. refresh is a post that skips the cache: FS-14.
29. facts and periods routes: FS-02.
30. unknown period is rejected: FS-01.
31. no authorizer user is 401 and nothing runs: FS-02.
32. service problem becomes RFC 9457 response: RFC 9457 errors.

--- test_summary_repository (4) ---
33. loads only the users posted and pending rows in the window: FS-02 / FS-03.
34. first posted date and account sync state: FS-23.
35. budget lines use the latest version per month: FS-08.
36. counts included transactions per period: FS-01 periods with no data.

--- test_detectors (13) ---
37. fees by type with three month average impact: FS-25.
38. refunded fees are excluded: FS-25.
39. free trial conversion: FS-26.
40. not a free trial: FS-26.
41. duplicate charge within 48 hours: FS-27.
42. refunded or far apart charges are not duplicates: FS-27.
43. habit that starts inside the period is not a duplicate: FS-27.
44. repeat same amount merchant is not a duplicate: FS-27.
45. small purchase leakage top two: FS-28.
46. leakage uses per month averages for multi month periods: FS-28.
~~47. velocity against budget and three month median: FS-30.~~ *Removed 2026-10-20: FS-30 removed.*
~~48. velocity is skipped before day seven: FS-30.~~ *Removed 2026-10-20: FS-30 removed.*
~~49. velocity does not apply to complete periods: FS-30.~~ *Removed 2026-10-20: FS-30 removed.*

--- test_framework (4) ---
50. score is dollars over cap capped at one and ranked: FS-24.
51. only top eight are kept: FS-24.
52. skipped and failing detectors do not stop the others: FS-24.
53. payload carries candidates and skipped detectors: FS-24.

--- test_anomalies_and_budgets (11) ---
54. anomaly against merchant median: FS-06.
55. falls back to category median with fewer than three merchant charges: FS-06.
56. at most five anomalies sorted by excess: FS-06.
57. less than 60 days history gives no anomalies and flag: FS-06.
58. new merchants have no posted transaction in the prior 12 months: FS-06.
59. budget items with pace for a complete period: FS-08.
60. multi month budget sums each months budget: FS-08.
61. multi month actual counts only months with a budget: FS-08.
~~62. month to date pace uses percent of period elapsed: FS-08.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
63. no budgets is unavailable and flagged: FS-08.
64. overall status rules: Appendix A overall_status rules.

--- test_cash_flow_and_categories (10) ---
65. income expenses net and changes: FS-04.
66. savings rate rounded to one decimal: FS-04.
67. zero income gives null savings rate and flag: FS-04.
68. zero comparison value gives null pct change: FS-04.
69. no comparison data nulls change fields and flags: FS-03 Alt no_comparison_data.
70. top three categories by spend: FS-05.
71. increases and decreases respect materiality: FS-05.
72. no comparison data leaves changes empty: FS-05.
73. uncategorized is its own category and flagged over 15 percent: FS-05.
74. uncategorized at 15 percent is not flagged: FS-05.

--- test_data_quality_and_payload (13) ---
75. transfers adjustments pending excluded and other currencies are left out: FS-23.
76. stale automatically synced account is flagged by ref: FS-23.
77. incomplete period flags accounts whose data stops early: FS-23.
~~78. incomplete period is not checked for month to date: FS-23.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
79. payload has contract fields and validates: FS-03.
80. unavailable budgets section is null in payload with flag: FS-08 / FS-09 unavailable section is null.
81. same inputs give identical payload and hash: FS-03.
82. hash ignores generated at but not data: FS-03.
83. validate rejects fields outside the allowlist: FS-16 allowlist schema.
84. every registered section takes only a period: FS-09.
85. section call with user id argument is rejected and logged: FS-02 Alt / FS-18 security event.
86. section call returns the section: FS-09.
87. unavailable section call returns available false: FS-09.

--- test_eval (21) ---
88. fixtures are in sync with the builder: FS-20.
89. at least twenty schema valid fixtures covering the required cases: FS-20.
90. every candidate type has a fixture that requires it: FS-20.
91. tiers are cumulative and core has the largest payload: FS-20.
92. grounded run passes and reports tokens and cost: FS-20.
93. any schema grounding or guardrail failure fails the run: FS-20.
94. followed injection fails the run: FS-20.
95. missing required insight types below 90 percent fails: FS-20.
96. token budget average and single summary limits: FS-20.
97. full tier needs two runs per fixture: FS-20.
98. estimate over the cap aborts before any call: FS-22.
99. confirm over cap runs anyway but stops once actual cost passes the cap: FS-22.
100. dry run counts tokens and prices each tier without calling the LLM: FS-22.
101. non production model produces the same report: FS-22.
102. version key changes with the model: FS-22.
103. results are saved pass or fail: FS-22.
104. tier order requires the previous tier to have passed: FS-22.
105. last pass is available for comparison: FS-22.
106. required check blocks ai changes without a full pass: FS-22.
107. required check paths cover prompt model and both schemas: FS-22.
108. fixture dir exists: FS-20.

--- test_generation (15) ---
109. success on first call: FS-10.
110. schema failure retries once with the errors: FS-10.
111. schema failure twice falls back: FS-10.
112. numbers in text share the single retry: FS-10.
113. no retry with less than ten seconds left: FS-10 deadline.
114. call timeout is capped by the remaining time: FS-10 deadline.
115. LLM failures fall back: FS-15.
116. grounding discard falls back: FS-15.
117. guardrail hits are reported: FS-12.
118. fallback summary uses templates and no numbers: FS-15.
119. fallback leaves out null metrics: FS-15.
120. estimate tokens is conservative: FS-21 input token count (Appendix C).
121. bedrock client calls converse with pinned model and caps: FS-10 pinned model / FS-21 caps.
122. bedrock errors become generic errors: FS-10 pinned model / FS-21 caps.
123. bedrock call slower than the timeout is a timeout: FS-10 pinned model / FS-21 caps.

--- test_log_redaction (2) ---
124. summary code has no redaction violations: FS-18 CI redaction check.
125. checker flags financial fields and LLM text: FS-18 CI redaction check.

--- test_periods (12) ---
126. this month compares same day range of previous month: FS-03 comparison rules. *(Still needed: the Dashboard's spending pace uses this rule.)*
127. this month on the 31st clamps to the shorter previous month: FS-03 comparison rules. *(Still needed: the Dashboard's spending pace uses this rule.)*
128. last month compares with the month before: FS-03 comparison rules.
129. last 3 months are complete calendar months: FS-03 comparison rules.
130. year to date compares same range last year: FS-03 comparison rules.
131. year to date on leap day compares with feb 28: FS-03 comparison rules.
132. last 12 months cross years: FS-03 comparison rules.
133. last month in january wraps to december: FS-03 comparison rules.
~~134. month to date percent elapsed: FS-08 pct_of_period_elapsed.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
135. today uses the users timezone: FS-03 user timezone.
136. unknown timezone falls back to utc: FS-03 user timezone.
137. labels: FS-01 comparison labels.

--- test_profile_client (5) ---
138. reads settings with a signed call: FS-03 / FS-23 profile settings (Appendix C).
139. caches settings for five minutes: FS-03 / FS-23 profile settings (Appendix C).
140. failure raises a generic error: FS-03 / FS-23 profile settings (Appendix C).
141. local mode without profile url uses local defaults: FS-03 / FS-23 profile settings (Appendix C).
142. missing profile url outside local is unavailable: FS-03 / FS-23 profile settings (Appendix C).

--- test_prompt_and_projection (7) ---
143. LLM view drops ids refs and timestamp: FS-16 minimum data.
144. LLM view does not change the payload: FS-16 minimum data.
145. system prompt sets scope data rules and examples: FS-12 / FS-16 system prompt.
146. facts go in one json data block never in instructions: FS-09 / FS-16.
147. static prompt is identical across users and marked for caching: FS-21 prompt caching.
148. retry message carries the validation errors: FS-10 retry with errors.
149. prompt template version is set: FS-14 / FS-18 prompt_template_version.

--- test_replay (2) ---
150. replay: FS-22 replay tests.
151. there are replays: FS-22 replay tests.

--- test_service (13) ---
152. generates an ai summary with facts audit snapshot and spend: FS-18 audit and snapshot / FS-21 spend.
153. same data is served from cache without an LLM call: FS-14.
154. new transactions change the hash and regenerate: FS-14.
155. refresh skips the cache and is limited to five a day: FS-14.
156. fewer than ten transactions skips the LLM: FS-15.
157. blocked call falls back and is audited: FS-21 / FS-18 blocked outcome.
158. LLM timeout falls back with reason: FS-15.
159. fallback is not cached: FS-14.
160. facts failure is an error and never calls the LLM: FS-15.
161. guardrail hits are written as security events: FS-18 security events.
162. logs never contain facts or LLM text: FS-18 logs carry no financial values.
163. periods list options with data and labels: FS-01.
164. facts only endpoint returns the payload: FS-13 facts render first.

--- test_store_guard_audit (15) ---
165. cached summary round trip with 30 day ttl: FS-14.
166. counter increment stops at the cap: FS-14 / FS-21 counters.
167. input over 8000 tokens is blocked: FS-21.
168. ten generations per user per day: FS-21.
169. daily budget reached blocks everyone until midnight utc: FS-21.
170. unset daily budget fails closed: FS-21.
171. unpriced model fails closed: FS-21.
172. budget store down fails closed: FS-21.
173. spend is recorded and alerts once at 80 percent: FS-21.
174. audit record has exactly the spec fields and 12 month ttl: FS-18.
175. snapshot kept 30 days keyed by payload and summary: FS-18.
176. security event is searchable by user: FS-18.
177. failed audit write is queued for retry and counted: FS-18.
178. retry handler writes queued items: FS-18.
179. account deletion purges user data and hashes audit ids: FS-18 account deletion.

--- test_validation (20) ---
180. valid output passes unchanged: FS-11.
181. not json is a schema error: FS-10.
182. json in a code fence is accepted: FS-10.
183. schema violations are reported: FS-10.
184. resolve path: FS-11.
185. unresolvable evidence drops insight and its recommendation: FS-11.
186. token must resolve to a number: FS-11.
187. null value does not resolve: FS-11.
188. budget insight is dropped when there are no budgets: FS-11.
189. metric alias highlight with null value is dropped: FS-11.
190. impact ref must resolve to a number: FS-11.
191. numbers in text ask for a retry when one is left: FS-11 digit rule / FS-10 shared retry.
192. numbers in text drop the item when the retry is used: FS-11 digit rule / FS-10 shared retry.
193. small numbers and tokens are allowed: FS-11 digit rule / FS-10 shared retry.
194. banned terms remove the item and count as guardrail hits: FS-12.
195. banned term match respects word boundaries: FS-12.
196. all recommendations removed leaves an empty section: FS-12.
197. half the items dropped discards the summary: FS-11.
198. bad headline discards when no retry is left: FS-11 digit rule / FS-10 shared retry.
199. banned term in headline discards the summary: FS-12.

--- AccountLastSyncedAtMigrationIT (fintracker-ledger) (2) ---
200. accounts.last_synced_at exists as a nullable timestamp with time zone: FS-23.
201. an account can be created without last_synced_at: FS-23.

--- test_internal_settings.TestGetSettingsByUserId (fintracker-user-profile) (2) ---
202. returns settings for known user: FS-03 / FS-23 profile settings.
203. raises when user has no settings: FS-03 / FS-23 profile settings.

--- test_internal_settings.TestInternalSettingsHandler (fintracker-user-profile) (6) ---
204. rejects call without iam identity: FS-02 Alt IAM authentication.
205. rejects caller not on allowlist: FS-02 Alt IAM authentication.
206. rejects every caller when allowlist is unset: FS-02 Alt, fail closed.
207. returns timezone and currency for allowed caller: FS-03 / FS-23.
208. unknown user returns 404 without internal detail: Exception Handling (CLAUDE.md).
209. malformed user id returns 400: RFC 9457 errors.

--- FinancialSummaryService (fintracker-ui) (4) ---
210. loads period options: FS-01.
211. loads facts first and the summary separately for a period: FS-13 facts render first.
212. refreshes with a POST: FS-14.
213. never sends a user ID, the server takes it from the session: FS-02.

--- summary-format (fintracker-ui) (8) ---
214. resolves facts paths, treating null as missing: FS-11 / FS-13.
215. formats money, percentages, percentage points and ratios: FS-13 currency and locale.
216. replaces tokens and metric aliases in text with formatted facts: FS-10 / FS-13 tokens.
217. shows a dash for a token that does not resolve: FS-13.
218. sorts insights warning, positive, info: FS-13 layout order.
219. turns data quality flags into fixed caveats with account nicknames: FS-13 / FS-23 caveats.
220. describes generation time relative to now: FS-14 generated timestamp.
221. lists the evidence facts behind an insight, without internal IDs: FS-13 Why? expander.

--- FinancialSummary (fintracker-ui) (12) ---
222. defaults to Last month and labels the comparison: FS-01.
223. disables periods with no data: FS-01 Alt.
224. renders headline, highlights, insights, recommendations, caveats and the disclaimer in order: FS-13 / FS-12 disclaimer.
225. hides empty sections: FS-13 Alt.
226. shows the evidence behind an insight under Why?: FS-13.
227. shows the generated time: FS-14.
228. shows the facts-only fallback with a Retry button: FS-15.
229. says there is not enough activity when the period is too quiet: FS-15 Alt.
230. keeps the previous summary visible with an inline error when loading fails: FS-01 Fail.
~~231. shows a Month to date badge for This month: FS-01 Alt.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
232. disables Refresh after the daily limit: FS-14 Alt.
233. refresh posts and replaces the summary: FS-14.

=========================
P2P TESTS (22)
=========================

--- test_tools (1) ---
1. generate insights fetches summary then calls bedrock once: existing behavior unchanged by the FS work.

--- test_clients.TestListTransactions (3) ---
2. maps ledger response to dataclasses: existing behavior unchanged by the FS work.
3. forwards user id as internal user id header: existing behavior unchanged by the FS work.
4. http error raises ledger client error not raw exception: existing behavior unchanged by the FS work.

--- test_clients.TestGetBudgetStatus (2) ---
5. maps budget and lines: existing behavior unchanged by the FS work.
6. 404 returns none not an error: existing behavior unchanged by the FS work.

--- test_clients.TestGetSavingsGoalProgress (3) ---
7. computes progress percentage: existing behavior unchanged by the FS work.
8. sends internal api key not a user header: existing behavior unchanged by the FS work.
9. zero target amount does not divide by zero: existing behavior unchanged by the FS work.

--- test_service (2) ---
10. generate ai insights nova micro success: existing behavior unchanged by the FS work.
11. generate ai insights falls back to claude: existing behavior unchanged by the FS work.

--- test_dashboard_balance (5) ---
12. overview total balance counts each account once: existing behavior unchanged by the FS work.
13. overview monthly totals unchanged by the balance fix: existing behavior unchanged by the FS work.
14. safe to spend counts each account and bill once: existing behavior unchanged by the FS work.
15. safe to spend subtracts pending money out: existing behavior unchanged by the FS work.
16. safe to spend ignores pending money in and posted rows: existing behavior unchanged by the FS work.

--- test_transaction_type_queries (6) ---
17. dashboard income counts only income: existing behavior unchanged by the FS work.
18. dashboard expenses are expense minus refund: existing behavior unchanged by the FS work.
19. dashboard expenses go negative when refunds exceed expenses: existing behavior unchanged by the FS work.
20. spending report nets refunds per category and counts only income: existing behavior unchanged by the FS work.
21. monthly trend uses income and net spend: existing behavior unchanged by the FS work.
22. insights summary nets refunds and skips non spending: existing behavior unchanged by the FS work.
