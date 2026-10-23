> **Tests for:** [AN-FS-financial-summary-spec.md](AN-FS-financial-summary-spec.md) · **Formerly:** `docs/fintracker-analytics/FS-tests.md` (renamed 2026-10)

=========================
F2P TESTS (289)
=========================

--- test_clients.TestIamSignedCalls (3) ---
1. ledger call is SigV4 signed: AN-FS-02 Alt, IAM-authenticated service calls.
2. budget call is SigV4 signed: AN-FS-02 Alt, IAM-authenticated service calls.
~~3. user profile call is SigV4 signed: AN-FS-02 Alt, IAM-authenticated service calls.~~ *Removed 2026-10-20: settings now arrive in the verified context (D23).*

--- test_tools (10) ---
4. no tool accepts a user id parameter: AN-FS-02 tools use the same mechanism.
5. tool without bound user is refused: AN-FS-02 tools use the same mechanism.
6. get dashboard overview combines overview and safe to spend: AN-FS-02 tools use the same mechanism.
7. get spending by category delegates to reports repository: AN-FS-02 tools use the same mechanism.
8. get monthly trend delegates to reports repository: AN-FS-02 tools use the same mechanism.
9. detect spending anomalies returns only anomalies slice: AN-FS-02 tools use the same mechanism.
10. detect subscription creep returns only creeps slice: AN-FS-02 tools use the same mechanism.
11. list transactions delegates to ledger client with all filters: AN-FS-02 tools use the same mechanism.
12. get budget status delegates to ledger client: AN-FS-02 tools use the same mechanism.
13. get savings goal progress delegates to user profile client: AN-FS-02 tools use the same mechanism.

--- test_identity (6) ---
14. reads internal user id from authorizer lambda context: AN-FS-02.
15. missing or blank authorizer user id is none: AN-FS-02.
16. local dev user id only when app env is local: AN-FS-02 local-dev identity (Alt).
17. startup refuses local dev user id outside local: AN-FS-02 local-dev identity (Alt).
18. startup allows local dev user id when local: AN-FS-02 local-dev identity (Alt).
19. tool context has no user until bound: AN-FS-02.

--- test_routes_auth (5) ---
20. dashboard uses authorizer user and ignores forged ids: AN-FS-02.
21. dashboard without authorizer user is 401 problem: AN-FS-02.
22. spending report uses authorizer user: AN-FS-02.
23. monthly trend without authorizer user is 401: AN-FS-02.
24. old insights endpoint is no longer served: AN-FS-13 old insights endpoint removed.

--- test_router (8) ---
25. ai insights endpoint returns generate insights result: AN-FS-02.
26. ai insights endpoint never leaks raw exception text: AN-FS-02.
27. summary uses the authorizer user and default period: AN-FS-02.
28. refresh is a post that skips the cache: AN-FS-14.
29. facts and periods routes: AN-FS-02.
30. unknown period is rejected: AN-FS-01.
31. no authorizer user is 401 and nothing runs: AN-FS-02.
32. service problem becomes RFC 9457 response: RFC 9457 errors.

--- test_summary_repository (4) ---
33. loads only the users posted and pending rows in the window: AN-FS-02 / AN-FS-03.
34. first posted date and account sync state: AN-FS-23.
35. budget lines use the latest version per month: AN-FS-08.
36. counts included transactions per period: AN-FS-01 periods with no data.

--- test_detectors (13) ---
37. fees by type with three month average impact: AN-FS-25.
38. refunded fees are excluded: AN-FS-25.
39. free trial conversion: AN-FS-26.
40. not a free trial: AN-FS-26.
41. duplicate charge within 48 hours: AN-FS-27.
42. refunded or far apart charges are not duplicates: AN-FS-27.
43. habit that starts inside the period is not a duplicate: AN-FS-27.
44. repeat same amount merchant is not a duplicate: AN-FS-27.
45. small purchase leakage top two: AN-FS-28.
46. leakage uses per month averages for multi month periods: AN-FS-28.
~~47. velocity against budget and three month median: AN-FS-30.~~ *Removed 2026-10-20: AN-FS-30 removed.*
~~48. velocity is skipped before day seven: AN-FS-30.~~ *Removed 2026-10-20: AN-FS-30 removed.*
~~49. velocity does not apply to complete periods: AN-FS-30.~~ *Removed 2026-10-20: AN-FS-30 removed.*

--- test_framework (4) ---
50. score is dollars over cap capped at one and ranked: AN-FS-24.
51. only top eight are kept: AN-FS-24.
52. skipped and failing detectors do not stop the others: AN-FS-24.
53. payload carries candidates and skipped detectors: AN-FS-24.

--- test_anomalies_and_budgets (11) ---
54. anomaly against merchant median: AN-FS-06.
55. falls back to category median with fewer than three merchant charges: AN-FS-06.
56. at most five anomalies sorted by excess: AN-FS-06.
57. less than 60 days history gives no anomalies and flag: AN-FS-06.
58. new merchants have no posted transaction in the prior 12 months: AN-FS-06.
59. budget items with pace for a complete period: AN-FS-08.
60. multi month budget sums each months budget: AN-FS-08.
61. multi month actual counts only months with a budget: AN-FS-08.
~~62. month to date pace uses percent of period elapsed: AN-FS-08.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
63. no budgets is unavailable and flagged: AN-FS-08.
64. overall status rules: Appendix A overall_status rules.

--- test_cash_flow_and_categories (10) ---
65. income expenses net and changes: AN-FS-04.
66. savings rate rounded to one decimal: AN-FS-04.
67. zero income gives null savings rate and flag: AN-FS-04.
68. zero comparison value gives null pct change: AN-FS-04.
69. no comparison data nulls change fields and flags: AN-FS-03 Alt no_comparison_data.
70. top three categories by spend: AN-FS-05.
71. increases and decreases respect materiality: AN-FS-05.
72. no comparison data leaves changes empty: AN-FS-05.
73. uncategorized is its own category and flagged over 15 percent: AN-FS-05.
74. uncategorized at 15 percent is not flagged: AN-FS-05.

--- test_data_quality_and_payload (13) ---
75. transfers adjustments pending excluded and other currencies are left out: AN-FS-23.
76. stale automatically synced account is flagged by ref: AN-FS-23.
77. incomplete period flags accounts whose data stops early: AN-FS-23.
~~78. incomplete period is not checked for month to date: AN-FS-23.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
79. payload has contract fields and validates: AN-FS-03.
80. unavailable budgets section is null in payload with flag: AN-FS-08 / AN-FS-09 unavailable section is null.
81. same inputs give identical payload and hash: AN-FS-03.
82. hash ignores generated at but not data: AN-FS-03.
83. validate rejects fields outside the allowlist: AN-FS-16 allowlist schema.
84. every registered section takes only a period: AN-FS-09.
85. section call with user id argument is rejected and logged: AN-FS-02 Alt / AN-FS-18 security event.
86. section call returns the section: AN-FS-09.
87. unavailable section call returns available false: AN-FS-09.

--- test_eval (21) ---
88. fixtures are in sync with the builder: AN-FS-20.
89. at least twenty schema valid fixtures covering the required cases: AN-FS-20.
90. every candidate type has a fixture that requires it: AN-FS-20.
91. tiers are cumulative and core has the largest payload: AN-FS-20.
92. grounded run passes and reports tokens and cost: AN-FS-20.
93. any schema grounding or guardrail failure fails the run: AN-FS-20.
94. followed injection fails the run: AN-FS-20.
95. missing required insight types below 90 percent fails: AN-FS-20.
96. token budget average and single summary limits: AN-FS-20.
97. full tier needs two runs per fixture: AN-FS-20.
98. estimate over the cap aborts before any call: AN-FS-22.
99. confirm over cap runs anyway but stops once actual cost passes the cap: AN-FS-22.
100. dry run counts tokens and prices each tier without calling the LLM: AN-FS-22.
101. non production model produces the same report: AN-FS-22.
102. version key changes with the model: AN-FS-22.
103. results are saved pass or fail: AN-FS-22.
104. tier order requires the previous tier to have passed: AN-FS-22.
105. last pass is available for comparison: AN-FS-22.
106. required check blocks ai changes without a full pass: AN-FS-22.
107. required check paths cover prompt model and both schemas: AN-FS-22.
108. fixture dir exists: AN-FS-20.

--- test_generation (15) ---
109. success on first call: AN-FS-10.
110. schema failure retries once with the errors: AN-FS-10.
111. schema failure twice falls back: AN-FS-10.
112. numbers in text share the single retry: AN-FS-10.
113. no retry with less than ten seconds left: AN-FS-10 deadline.
114. call timeout is capped by the remaining time: AN-FS-10 deadline.
115. LLM failures fall back: AN-FS-15.
116. grounding discard falls back: AN-FS-15.
117. guardrail hits are reported: AN-FS-12.
118. fallback summary uses templates and no numbers: AN-FS-15.
119. fallback leaves out null metrics: AN-FS-15.
120. estimate tokens is conservative: AN-FS-21 input token count (Appendix C).
121. bedrock client calls converse with pinned model and caps: AN-FS-10 pinned model / AN-FS-21 caps.
122. bedrock errors become generic errors: AN-FS-10 pinned model / AN-FS-21 caps.
123. bedrock call slower than the timeout is a timeout: AN-FS-10 pinned model / AN-FS-21 caps.

--- test_log_redaction (2) ---
124. summary code has no redaction violations: AN-FS-18 CI redaction check.
125. checker flags financial fields and LLM text: AN-FS-18 CI redaction check.

--- test_periods (12) ---
126. this month compares same day range of previous month: AN-FS-03 comparison rules. *(Still needed: the Dashboard's spending pace uses this rule.)*
127. this month on the 31st clamps to the shorter previous month: AN-FS-03 comparison rules. *(Still needed: the Dashboard's spending pace uses this rule.)*
128. last month compares with the month before: AN-FS-03 comparison rules.
129. last 3 months are complete calendar months: AN-FS-03 comparison rules.
130. year to date compares same range last year: AN-FS-03 comparison rules.
131. year to date on leap day compares with feb 28: AN-FS-03 comparison rules.
132. last 12 months cross years: AN-FS-03 comparison rules.
133. last month in january wraps to december: AN-FS-03 comparison rules.
~~134. month to date percent elapsed: AN-FS-08 pct_of_period_elapsed.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
135. today uses the users timezone: AN-FS-03 user timezone.
136. unknown timezone falls back to utc: AN-FS-03 user timezone.
137. labels: AN-FS-01 comparison labels.

--- test_profile_client (5) ---
138. reads settings with a signed call: AN-FS-03 / AN-FS-23 profile settings (Appendix C).
139. caches settings for five minutes: AN-FS-03 / AN-FS-23 profile settings (Appendix C).
140. failure raises a generic error: AN-FS-03 / AN-FS-23 profile settings (Appendix C).
141. local mode without profile url uses local defaults: AN-FS-03 / AN-FS-23 profile settings (Appendix C).
142. missing profile url outside local is unavailable: AN-FS-03 / AN-FS-23 profile settings (Appendix C).

--- test_prompt_and_projection (7) ---
143. LLM view drops ids refs and timestamp: AN-FS-16 minimum data.
144. LLM view does not change the payload: AN-FS-16 minimum data.
145. system prompt sets scope data rules and examples: AN-FS-12 / AN-FS-16 system prompt.
146. facts go in one json data block never in instructions: AN-FS-09 / AN-FS-16.
147. static prompt is identical across users and marked for caching: AN-FS-21 prompt caching.
148. retry message carries the validation errors: AN-FS-10 retry with errors.
149. prompt template version is set: AN-FS-14 / AN-FS-18 prompt_template_version.

--- test_replay (2) ---
150. replay: AN-FS-22 replay tests.
151. there are replays: AN-FS-22 replay tests.

--- test_service (13) ---
152. generates an ai summary with facts audit snapshot and spend: AN-FS-18 audit and snapshot / AN-FS-21 spend.
153. same data is served from cache without an LLM call: AN-FS-14.
154. new transactions change the hash and regenerate: AN-FS-14.
155. refresh skips the cache and is limited to five a day: AN-FS-14.
156. fewer than ten transactions skips the LLM: AN-FS-15.
157. blocked call falls back and is audited: AN-FS-21 / AN-FS-18 blocked outcome.
158. LLM timeout falls back with reason: AN-FS-15.
159. fallback is not cached: AN-FS-14.
160. facts failure is an error and never calls the LLM: AN-FS-15.
161. guardrail hits are written as security events: AN-FS-18 security events.
162. logs never contain facts or LLM text: AN-FS-18 logs carry no financial values.
163. periods list options with data and labels: AN-FS-01.
164. facts only endpoint returns the payload: AN-FS-13 facts render first.

--- test_store_guard_audit (15) ---
165. cached summary round trip with 30 day ttl: AN-FS-14.
166. counter increment stops at the cap: AN-FS-14 / AN-FS-21 counters.
167. input over 8000 tokens is blocked: AN-FS-21.
168. ten generations per user per day: AN-FS-21.
169. daily budget reached blocks everyone until midnight utc: AN-FS-21.
170. unset daily budget fails closed: AN-FS-21.
171. unpriced model fails closed: AN-FS-21.
172. budget store down fails closed: AN-FS-21.
173. spend is recorded and alerts once at 80 percent: AN-FS-21.
174. audit record has exactly the spec fields and 12 month ttl: AN-FS-18.
175. snapshot kept 30 days keyed by payload and summary: AN-FS-18.
176. security event is searchable by user: AN-FS-18.
177. failed audit write is queued for retry and counted: AN-FS-18.
178. retry handler writes queued items: AN-FS-18.
179. account deletion purges user data and hashes audit ids: AN-FS-18 account deletion.

--- test_validation (20) ---
180. valid output passes unchanged: AN-FS-11.
181. not json is a schema error: AN-FS-10.
182. json in a code fence is accepted: AN-FS-10.
183. schema violations are reported: AN-FS-10.
184. resolve path: AN-FS-11.
185. unresolvable evidence drops insight and its recommendation: AN-FS-11.
186. token must resolve to a number: AN-FS-11.
187. null value does not resolve: AN-FS-11.
188. budget insight is dropped when there are no budgets: AN-FS-11.
189. metric alias highlight with null value is dropped: AN-FS-11.
190. impact ref must resolve to a number: AN-FS-11.
191. numbers in text ask for a retry when one is left: AN-FS-11 digit rule / AN-FS-10 shared retry.
192. numbers in text drop the item when the retry is used: AN-FS-11 digit rule / AN-FS-10 shared retry.
193. small numbers and tokens are allowed: AN-FS-11 digit rule / AN-FS-10 shared retry.
194. banned terms remove the item and count as guardrail hits: AN-FS-12.
195. banned term match respects word boundaries: AN-FS-12.
196. all recommendations removed leaves an empty section: AN-FS-12.
197. half the items dropped discards the summary: AN-FS-11.
198. bad headline discards when no retry is left: AN-FS-11 digit rule / AN-FS-10 shared retry.
199. banned term in headline discards the summary: AN-FS-12.

--- AccountLastSyncedAtMigrationIT (fintracker-ledger) (2) ---
200. accounts.last_synced_at exists as a nullable timestamp with time zone: AN-FS-23.
201. an account can be created without last_synced_at: AN-FS-23.

--- test_internal_settings.TestGetSettingsByUserId (fintracker-user-profile) (2) ---
202. returns settings for known user: AN-FS-03 / AN-FS-23 profile settings.
203. raises when user has no settings: AN-FS-03 / AN-FS-23 profile settings.

--- test_internal_settings.TestInternalSettingsHandler (fintracker-user-profile) (6) ---
204. rejects call without iam identity: AN-FS-02 Alt IAM authentication.
205. rejects caller not on allowlist: AN-FS-02 Alt IAM authentication.
206. rejects every caller when allowlist is unset: AN-FS-02 Alt, fail closed.
207. returns timezone and currency for allowed caller: AN-FS-03 / AN-FS-23.
208. unknown user returns 404 without internal detail: Exception Handling (CLAUDE.md).
209. malformed user id returns 400: RFC 9457 errors.

--- FinancialSummaryService (fintracker-ui) (4) ---
210. loads period options: AN-FS-01.
211. loads facts first and the summary separately for a period: AN-FS-13 facts render first.
212. refreshes with a POST: AN-FS-14.
213. never sends a user ID, the server takes it from the session: AN-FS-02.

--- summary-format (fintracker-ui) (8) ---
214. resolves facts paths, treating null as missing: AN-FS-11 / AN-FS-13.
215. formats money, percentages, percentage points and ratios: AN-FS-13 currency and locale.
216. replaces tokens and metric aliases in text with formatted facts: AN-FS-10 / AN-FS-13 tokens.
217. shows a dash for a token that does not resolve: AN-FS-13.
218. sorts insights warning, positive, info: AN-FS-13 layout order.
219. turns data quality flags into fixed caveats with account nicknames: AN-FS-13 / AN-FS-23 caveats.
220. describes generation time relative to now: AN-FS-14 generated timestamp.
221. lists the evidence facts behind an insight, without internal IDs: AN-FS-13 Why? expander.

--- FinancialSummary (fintracker-ui) (12) ---
222. defaults to Last month and labels the comparison: AN-FS-01.
223. disables periods with no data: AN-FS-01 Alt.
224. renders headline, highlights, insights, recommendations, caveats and the disclaimer in order: AN-FS-13 / AN-FS-12 disclaimer.
225. hides empty sections: AN-FS-13 Alt.
226. shows the evidence behind an insight under Why?: AN-FS-13.
227. shows the generated time: AN-FS-14.
228. shows the facts-only fallback with a Retry button: AN-FS-15.
229. says there is not enough activity when the period is too quiet: AN-FS-15 Alt.
230. keeps the previous summary visible with an inline error when loading fails: AN-FS-01 Fail.
~~231. shows a Month to date badge for This month: AN-FS-01 Alt.~~ *Removed 2026-10-20: This month is no longer a Reports period.*
232. disables Refresh after the daily limit: AN-FS-14 Alt.
233. refresh posts and replaces the summary: AN-FS-14.

--- test_periods (2026-10-21 additions) (5) ---
234. this month is not a reports period: AN-FS-01 Requirement.
235. month to date compares the same day range of the previous month: AN-FS-03 comparison rules.
236. month to date on the 31st clamps to the shorter previous month: AN-FS-03 comparison rules.
237. month to date on the first covers one day each: AN-FS-03 comparison rules.
238. month to date in january compares with december: AN-FS-03 comparison rules.

--- test_service (2026-10-21 additions) (1) ---
239. periods list the four reports options with data flags and labels: AN-FS-01 Happy.

--- test_anomalies_and_budgets (2026-10-21 additions) (2) ---
240. pct of period elapsed is always null: AN-FS-08 Requirement, Appendix A.
241. budget lines match spend by category id so a renamed category keeps its spend: AN-FS-08 Happy, XS-RPTV-02.

--- test_data_quality_and_payload (2026-10-21 additions) (1) ---
242. incomplete period is checked only for complete periods: AN-FS-23 Fail.

--- test_recurring (17) ---
243. three charges with a regular cadence and steady amount are recurring: AN-FS-07 Happy.
244. fewer than three charges are not recurring: AN-FS-07 Happy.
245. an irregular cadence is not recurring: AN-FS-07 Happy.
246. amounts more than ten percent apart are not recurring: AN-FS-07 Happy.
247. a cadence off by three days still counts: AN-FS-07 Happy.
248. a price increase is reported when the latest charge is over five percent higher: AN-FS-07 Happy.
249. a small increase inside the tolerance is also reported: AN-FS-07 Happy.
250. an increase of five percent or less is not a price increase: AN-FS-07 Happy.
251. a subscription that just became recurring is new and an old one is not: AN-FS-07 Requirement.
252. other cadences are normalised to a monthly total: AN-FS-07 Requirement.
253. a subscription that stopped is not counted: AN-FS-07 Requirement.
254. pending charges do not count toward a recurring series: AN-FS-07 Requirement, AN-FS-23.
255. a recurring charge due in the next 30 days is an upcoming bill: AN-FS-07 Alt.
256. bills are sorted by due date and those beyond 30 days are left out: AN-FS-07 Alt.
257. a bill whose next charge is already in the past is not upcoming: AN-FS-07 Alt.
258. recurring sections are registered and take only a period: AN-FS-09 Happy.
259. the payload carries recurring and upcoming bills: AN-FS-07 Requirement, Appendix A.

--- test_emergency_fund (7) ---
260. coverage is liquid savings over the average of the last three complete months: AN-FS-19 Happy.
261. status thresholds: AN-FS-19 Happy.
262. refunds net against the average: AN-FS-19 Happy, AN-FS-23.
263. no account selected as liquid savings is unavailable and flagged: AN-FS-19 Alt.
264. fewer than three complete months of history is unavailable: AN-FS-19 Alt.
265. an average of zero expenses is unavailable: AN-FS-19 Alt.
266. overall status is needs attention when the emergency fund is: AN-FS-19 Alt, Appendix A overall_status.

--- test_cash_timing (7) ---
267. a projected low below the threshold is a candidate: AN-FS-29 Happy.
268. a comfortable balance has no candidate: AN-FS-29 Happy.
269. no balance data skips the detector: AN-FS-29 Alt.
270. no detectable payday skips the detector: AN-FS-29 Alt.
271. a single deposit is not a payday: AN-FS-29 Happy.
272. irregular deposits are not a payday: AN-FS-29 Happy.
273. bills due after payday do not count: AN-FS-29 Happy.

--- test_validation (fintracker-ai-assistant) (2) ---
274. the insight types added with the recurring, emergency fund and cash timing requirements are accepted: AN-FS-07 / AN-FS-19 / AN-FS-29, Appendix B note.
275. the metrics added with the recurring and emergency fund requirements are accepted: AN-FS-07 / AN-FS-19, Appendix B note.

--- FinancialSummary (fintracker-ui, 2026-10-21 additions) (3) ---
276. labels the period and its comparison: AN-FS-01 Happy.
277. has no period selector of its own, the page owns it: AN-RPT-01 Requirement.
278. reloads facts and summary when the page changes the period: AN-RPT-01 Requirement.

--- cost_guard.tftest.hcl (fintracker-ai-assistant) (6) ---
279. budget alerts at 50, 80 and 100 percent of the monthly budget: AN-FS-21 Account level.
280. at 100 percent a deny policy is attached to every bedrock role: AN-FS-21 Account level.
281. cost anomaly detection watches bedrock spend: AN-FS-21 Account level.
282. the budget action role can only attach the deny policy to the listed roles: AN-FS-21 Account level.
283. an unset or zero budget is refused: AN-FS-21 Fail.
284. no alert address is refused: AN-FS-21 Fail.

--- roles.tftest.hcl (fintracker-ai-assistant) (5) ---
285. the evaluation role is assumable only from the protected environment: AN-FS-22 Fail, AN-FS-21 separate roles.
286. the app role is assumable by the compute service only: AN-FS-21 separate roles.
287. bedrock calls are limited to the listed models: AN-FS-21 separate roles.
288. a wildcard model is refused: AN-FS-21 separate roles.
289. the cost guard receives every role that can call bedrock: AN-FS-21 Account level.

=========================
P2P TESTS (22)
=========================

--- test_tools (1) ---
1. generate insights fetches summary then calls bedrock once: existing behavior unchanged by the AN-FS work.

--- test_clients.TestListTransactions (3) ---
2. maps ledger response to dataclasses: existing behavior unchanged by the AN-FS work.
3. forwards user id as internal user id header: existing behavior unchanged by the AN-FS work.
4. http error raises ledger client error not raw exception: existing behavior unchanged by the AN-FS work.

--- test_clients.TestGetBudgetStatus (2) ---
5. maps budget and lines: existing behavior unchanged by the AN-FS work.
6. 404 returns none not an error: existing behavior unchanged by the AN-FS work.

--- test_clients.TestGetSavingsGoalProgress (3) ---
7. computes progress percentage: existing behavior unchanged by the AN-FS work.
8. sends internal api key not a user header: existing behavior unchanged by the AN-FS work.
9. zero target amount does not divide by zero: existing behavior unchanged by the AN-FS work.

--- test_service (2) ---
10. generate ai insights nova micro success: existing behavior unchanged by the AN-FS work.
11. generate ai insights falls back to claude: existing behavior unchanged by the AN-FS work.

--- test_dashboard_balance (5) ---
~~12. overview total balance counts each account once: existing behavior unchanged by the AN-FS work.~~ *Removed 2026-10-21: Analytics no longer serves Dashboard totals (AN-RPT-10).*
~~13. overview monthly totals unchanged by the balance fix: existing behavior unchanged by the AN-FS work.~~ *Removed 2026-10-21: Analytics no longer serves Dashboard totals (AN-RPT-10).*
~~14. safe to spend counts each account and bill once: existing behavior unchanged by the AN-FS work.~~ *Removed 2026-10-21: Analytics no longer serves Dashboard totals (AN-RPT-10).*
~~15. safe to spend subtracts pending money out: existing behavior unchanged by the AN-FS work.~~ *Removed 2026-10-21: Analytics no longer serves Dashboard totals (AN-RPT-10).*
~~16. safe to spend ignores pending money in and posted rows: existing behavior unchanged by the AN-FS work.~~ *Removed 2026-10-21: Analytics no longer serves Dashboard totals (AN-RPT-10).*

--- test_transaction_type_queries (6) ---
17. dashboard income counts only income: existing behavior unchanged by the AN-FS work.
18. dashboard expenses are expense minus refund: existing behavior unchanged by the AN-FS work.
19. dashboard expenses go negative when refunds exceed expenses: existing behavior unchanged by the AN-FS work.
20. spending report nets refunds per category and counts only income: existing behavior unchanged by the AN-FS work.
21. monthly trend uses income and net spend: existing behavior unchanged by the AN-FS work.
22. insights summary nets refunds and skips non spending: existing behavior unchanged by the AN-FS work.
