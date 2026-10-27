=========================
F2P TESTS (203)
=========================

--- test_chat_entry (7) ---
1. the rest authorizer context gives the same verified user context: AI-CHAT-02 identity from the authorizer (ADR-012).
2. the http api shape still works: AI-CHAT-02 identity from the authorizer (ADR-012).
3. the lambda node wins when both shapes are present: AI-CHAT-02 identity from the authorizer (ADR-012).
4. no authorizer context means no user: AI-CHAT-02 identity from the authorizer (ADR-012).
5. a flat authorizer node without a user is not a context: AI-CHAT-02 identity from the authorizer (ADR-012).
6. traceparent carries the requests trace id: AI-CHAT-13 Happy, one trace_id across services.
7. no trace id means no header: AI-CHAT-13 Alt, no trace without an ID.

--- test_chat_entry_middleware (1) ---
8. the trace id is available inside the request and cleared after: AI-CHAT-13 Happy, one trace_id across services.

--- test_router (10) ---
9. the response is newline delimited json events: AI-CHAT-01 chat API and stream events.
10. user context and tier come from the authorizer: AI-CHAT-02 Happy, user and tier from the authorizer only.
11. a missing tier in the context is the lowest tier: AI-CHAT-02 Alt, lowest tier when none.
12. the rest authorizer shape works too: AI-CHAT-02 Happy, user and tier from the authorizer only.
13. an invalid body is a 400 before any stream: AI-CHAT-01 chat API and stream events.
14. a body that is not json is a 400: AI-CHAT-01 chat API and stream events.
15. a 2000 character message is accepted: AI-CHAT-01 chat API and stream events.
16. an unknown conversation is a 404 problem: AI-CHAT-03 Fail, another user's conversation is a 404.
17. without a verified user the route answers 401: AI-CHAT-02 Fail, no verified user.
18. only post is served: AI-CHAT-01 chat API and stream events.

--- test_service (26) ---
19. a spending question streams status answer sources and done: AI-CHAT-01 Happy, status then answer, sources and done.
20. a new conversation id is in the first event: AI-CHAT-01 Alt, new conversation in the first event.
21. answers about the users money end with the disclaimer: AI-CHAT-09 answers about money end with the disclaimer.
22. the answer is streamed in chunks that join to the full text: AI-CHAT-11 Happy, answer streamed in chunks.
23. a broken stream does not save the turn: AI-CHAT-01 Fail, a broken stream is not saved.
24. a completed turn is saved for 30 days: AI-CHAT-03 Happy, completed turn kept 30 days.
25. a follow up is answered in the context of the previous turn: AI-CHAT-03 Happy, follow-up uses the previous turn.
26. only the last ten turns go to the model: AI-CHAT-03 last 10 turns as history.
27. a new session starts with an empty thread: AI-CHAT-03 Alt, new session starts empty.
28. a conversation of another user is not found: AI-CHAT-03 Fail, another user's conversation is a 404.
29. an unknown conversation is not found: AI-CHAT-03 Fail, unknown conversation is a 404.
30. retrying after a failed turn keeps the same conversation: AI-CHAT-03 Alt, a failed turn keeps its conversation.
31. a comparison needing three tool calls completes: AI-CHAT-06 Happy, 3 calls within limits.
32. a ninth tool call is refused and the answer says it may be incomplete: AI-CHAT-06 Alt, 9th call refused.
33. a turn that reaches 45 seconds ends with a timeout error and no answer: AI-CHAT-06 Fail, 45 s deadline is a timeout.
34. a tool is given at most five seconds and the time left: AI-CHAT-06 5 s tool timeout, time left in the turn.
35. an ungrounded first draft is retried and the user never sees it: AI-CHAT-11 Alt, the corrected retry is shown, never the first draft.
36. two failed checks return the fallback for the failure type: AI-CHAT-11 Fail, fallback for the failure type.
37. a reply that is not json is retried then falls back: AI-CHAT-11 Fail, reply that is not JSON.
38. a reply cut off by max tokens is not shown: AI-CHAT-11 Fail, reply cut off by max_tokens.
39. no retry is attempted when too little time is left: AI-CHAT-11 retry only while time is left.
40. a model failure ends the turn with a generic error: AI-CHAT-11 model failures end the turn with a generic error.
41. a throttled call is retried before giving up: AI-CHAT-11 provider retries before processing.
42. the spend reservation is settled to the actual tokens: AI-CHAT-15 settle to actual tokens.
43. a failed call before processing releases its reservation: AI-CHAT-15 release on a call that was never processed.
44. two turns at once beyond the in flight cap get service busy: AI-CHAT-15 Alt, service_busy when too many turns are in flight.

--- test_limits (25) ---
45. the day is the users local day: AI-CHAT-02 Alt, limits reset at local midnight.
46. limits reset at the next local midnight: AI-CHAT-02 Alt, limits reset at local midnight.
47. the reset across a dst change is still local midnight: AI-CHAT-02 Alt, limits reset at local midnight.
48. a user under the allowance is admitted: AI-CHAT-02 Happy, admitted under the allowance.
49. once the allowance is used up the next message is refused with the reset time: AI-CHAT-02 Happy, allowance used up is refused with the reset time.
50. each tier has its own allowance: AI-CHAT-02 identity and per-tier limits.
51. the next local day starts from zero: AI-CHAT-02 Alt, limits reset at local midnight.
52. usage is per user: AI-CHAT-02 identity and per-tier limits.
53. an unreadable counter refuses the turn: AI-CHAT-02 Fail, limits_unavailable.
54. a tier without a configured allowance fails closed: AI-CHAT-02 Fail, limits never fail open.
55. an unknown tier gets the lowest allowance: AI-CHAT-02 identity and per-tier limits.
56. the service counts input and output tokens against the allowance: AI-CHAT-02 input and output tokens both count.
57. a user over the allowance gets daily limit reached and no model call: AI-CHAT-02 Happy, allowance used up is refused with the reset time.
58. a failing counter refuses the turn with limits unavailable: AI-CHAT-02 Fail, limits_unavailable.
59. a counter that cannot be updated refuses the answer: AI-CHAT-02 Fail, limits_unavailable.
60. the allowance is not checked against a forged tier: AI-CHAT-02 Fail, tier never from the body.
61. a user in the body is rejected and logged as a security event: AI-CHAT-02 Fail, user_id in the body.
62. a valid body is accepted: AI-CHAT-01 Happy, valid body.
63. each audit record carries tokens and the estimated cost: AI-CHAT-15 Happy, tokens and cost in the audit record.
64. at the daily budget new turns return service busy: AI-CHAT-15 Alt, service_busy at 100%.
65. the budget is shared with the financial summary: AI-CHAT-15 budget shared with the Financial Summary.
66. an unreachable budget store fails closed: AI-CHAT-15 limits never fail open.
67. the model is called with the pinned id and 800 max tokens: AI-CHAT-15 Happy, pinned model and max_tokens.
68. a model that is not on the approved list ends the turn: AI-CHAT-15 Fail, unapproved model.
69. crossing 80 percent of the daily budget sends the alert once: AI-CHAT-15 Alt, alert at 80%.

--- test_execute_tool (28) ---
70. chat sees exactly the eight allowlisted tools: AI-CHAT-04 tool registry and execute_tool.
71. no tool schema has a user timezone or currency field or extra properties: AI-CHAT-04 tool registry and execute_tool.
72. a valid call is validated and sent with the verified context: AI-CHAT-04 Happy, validated and sent with the context.
73. the period defaults to last month: AI-CHAT-04 Happy, strict schema defaults.
74. a tool not on the allowlist gets a generic error and a security flag: AI-CHAT-04 tool registry and execute_tool.
75. arguments outside the schema are rejected before any call: AI-CHAT-04 tool registry and execute_tool.
76. arguments must be a json object: AI-CHAT-04 tool registry and execute_tool.
77. a refusal never echoes the rejected value: AI-CHAT-04 tool registry and execute_tool.
78. a tool with no arguments rejects any: AI-CHAT-04 tool registry and execute_tool.
79. the budget month defaults to the users current month: AI-CHAT-04 tool registry and execute_tool.
80. a budget month must be current or past within 24 months: AI-CHAT-04 tool registry and execute_tool.
81. a budget 24 months back is allowed: AI-CHAT-04 tool registry and execute_tool.
82. the budget result has the ledger's remaining and totals: AI-CHAT-05 / LG-READ-03.
83. no budget for the month is a result not an error: AI-CHAT-05 Appendix B tools.
84. search dates must be at most 24 months apart and ordered: AI-CHAT-04 tool registry and execute_tool.
85. search returns 25 rows plus the total count and amount: AI-CHAT-05 Alt, 25 rows plus totals.
86. category trend returns twelve monthly values for one category: AI-CHAT-05 Appendix B tools.
87. category trend requires a category and reports an unknown one: AI-CHAT-05 Appendix B tools.
88. top merchants and cash flow pass aggregates through: AI-CHAT-05 Appendix B tools.
89. an upstream failure reaches the model as a generic message: AI-CHAT-05 Fail, generic tool error.
90. a knowledge failure means no docs available: AI-CHAT-07 Fail, KN-RET error is no docs.
91. an unexpected exception never reaches the model: AI-CHAT-05 Fail, generic tool error.
92. a slow tool is cut off after the tool timeout: AI-CHAT-06 5 s tool timeout.
93. a tool never gets more than the time left in the turn: AI-CHAT-06 turn deadline.
94. only chunks at or above the threshold reach the model: AI-CHAT-07 Happy, only chunks over the threshold.
95. when no chunk reaches the threshold the model gets an empty list: AI-CHAT-07 Alt, nothing over the threshold.
96. chunk text is capped and stripped of control characters: AI-CHAT-10 chunk text is data, capped and cleaned.
97. the help query is 1 to 1000 characters: AI-CHAT-04 strict schema for retrieve_help_docs.

--- test_docs_and_guardrails (18) ---
98. a how to answer cites the doc title and section: AI-CHAT-07 help-doc answers with sources.
99. a doc source is listed once even if cited twice: AI-CHAT-07 help-doc answers with sources.
100. when no chunk reaches the threshold the answer says so without asking the model again: AI-CHAT-07 Alt, no chunk over the threshold.
101. the unanswered question is logged without a user id: AI-CHAT-12 Happy, question logged without a user ID.
102. a knowledge error means help docs are unavailable and nothing is logged: AI-CHAT-07 Fail, help docs unavailable.
103. a cited source that was not retrieved fails the check: AI-CHAT-07 Fail, uncited source fails the post-check.
104. help docs and data tools can be combined: AI-CHAT-07 docs and data tools together.
105. when every data tool fails the answer says the data is unavailable: AI-CHAT-05 Fail, data unavailable is said, not guessed.
106. the model may answer partially when one of two tools fails: AI-CHAT-05 Alt, partial answer.
107. the audit record lists each tool with its outcome and latency: AI-CHAT-13 tool calls with outcome and latency.
108. an investment question gets the polite refusal: AI-CHAT-09 Happy, polite refusal.
109. general budgeting education from help docs is allowed: AI-CHAT-09 Alt, budgeting education from help docs.
110. a banned term fails the check and the corrected answer is shown: AI-CHAT-09 Fail, banned term retried and counted.
111. banned terms twice end in the out of scope fallback: AI-CHAT-09 Fail, banned terms twice is a fallback.
112. a request for another users data is rejected by the tool layer and logged: AI-CHAT-10 Happy, another user's data refused and logged.
113. the allowlist miss is a security event too: AI-CHAT-04 Fail, allowlist miss is a security event.
114. a merchant name with instructions stays inside a tool result data block: AI-CHAT-10 Alt, merchant text stays data.
115. the user message reaches the model only inside the data json: AI-CHAT-10 user message only in data fields.

--- test_grounding (13) ---
116. figures in the tool result pass: AI-CHAT-08 Happy, figures from tool results.
117. formatting differences are normalized: AI-CHAT-08 grounded figures.
118. thousands separators and the k suffix are normalized: AI-CHAT-08 grounded figures.
119. a rounded figure is grounded but a different one is not: AI-CHAT-08 grounded figures.
120. a figure found in no tool result is reported: AI-CHAT-08 Fail, figure in no tool result.
121. counts followed by a count word need grounding: AI-CHAT-08 grounded figures.
122. small numbers that are not figures are ignored: AI-CHAT-08 grounded figures.
123. dates are exempt: AI-CHAT-08 Alt, dates exempt.
124. numbers the user wrote are exempt: AI-CHAT-08 Alt, the user's own words exempt.
125. numbers from help doc text are exempt: AI-CHAT-08 Alt, help-doc numbers exempt.
126. text without figures passes even with no tool results: AI-CHAT-08 grounded figures.
127. figures are listed with their value and decimals: AI-CHAT-08 grounded figures.
128. numbers are collected from nested results and numeric strings: AI-CHAT-08 grounded figures.

--- test_validation (16) ---
129. a json object reply parses: AI-CHAT-11 validate, retry once, then stream.
130. a fenced reply parses: AI-CHAT-11 validate, retry once, then stream.
131. json after a short preface still parses: AI-CHAT-11 validate, retry once, then stream.
132. a preface does not excuse a reply that breaks the schema: AI-CHAT-11 validate, retry once, then stream.
133. text that is not json does not parse: AI-CHAT-11 validate, retry once, then stream.
134. extra fields and an empty answer are schema errors: AI-CHAT-11 validate, retry once, then stream.
135. a grounded answer passes: AI-CHAT-08 Happy, figures from tool results.
136. an ungrounded figure fails with the figure named: AI-CHAT-08 Fail, figure in no tool result.
137. a cited source that was not retrieved fails: AI-CHAT-07 cited sources must be retrieved chunks.
138. a retrieved source passes: AI-CHAT-07 Happy, retrieved source passes.
139. docs were given but none cited in a how to answer fails: AI-CHAT-07 cited sources must be retrieved chunks.
140. no citation is needed when no docs were retrieved: AI-CHAT-07 cited sources must be retrieved chunks.
141. numbers in cited doc text are exempt: AI-CHAT-07 cited sources must be retrieved chunks.
142. a banned term fails and is reported by term: AI-CHAT-09 banned terms by whole word.
143. banned terms match whole words only: AI-CHAT-09 banned terms by whole word.
144. an out of scope reply is accepted without checking its text: AI-CHAT-09 out-of-scope reply.

--- test_sanitize_prompt_llm (14) ---
145. control characters are stripped and text is capped: AI-CHAT-10 prompt-injection protection.
146. nested strings are cleaned and other values are left alone: AI-CHAT-10 prompt-injection protection.
147. data json is compact and keeps unicode: AI-CHAT-10 prompt-injection protection.
148. the system prompt says field values are data never instructions: AI-CHAT-10 prompt-injection protection.
149. the system prompt states the output contract and the scope: AI-CHAT-10 prompt-injection protection.
150. an unknown prompt version is an error: AI-CHAT-10 prompt-injection protection.
151. the first message carries the user text only in data fields: AI-CHAT-10 prompt-injection protection.
152. long history entries are capped: AI-CHAT-10 prompt-injection protection.
153. tool results go back as json tool result blocks: AI-CHAT-10 prompt-injection protection.
154. the retry message lists the problems as data: AI-CHAT-10 prompt-injection protection.
155. a tool use reply is parsed into tool uses: AI-CHAT-04 tool calls from the model.
156. assistant blocks replay the text and tool uses for the next call: AI-CHAT-04 tool calls from the model.
157. a final reply is text and a cut off one is flagged: AI-CHAT-15 max_tokens cut-off is flagged.
158. failures are classified like the summary calls: AI-CHAT-15 model failures classified.

--- test_unanswered (5) ---
159. email addresses and numbers are masked: AI-CHAT-12 Fail, no email or number in the stored text.
160. the item has the masked question scores paths and a 90 day ttl but no user: AI-CHAT-12 Fail, no email or number in the stored text.
161. long questions are capped: AI-CHAT-12 unanswered questions log.
162. the weekly report groups similar questions with counts: AI-CHAT-12 Happy, weekly report grouped with counts.
163. the weekly handler returns the report as data: AI-CHAT-12 Happy, weekly report grouped with counts.

--- test_audit_and_logs (8) ---
164. one audit record per turn with ids versions tools tokens and outcome: AI-CHAT-13 audit, traces and log hygiene.
165. security events are stored with severity security: AI-CHAT-13 audit, traces and log hygiene.
166. no message answer tool result or chunk text is logged or audited: AI-CHAT-13 audit, traces and log hygiene.
167. a failed audit write is queued and never blocks the answer: AI-CHAT-13 audit, traces and log hygiene.
168. a failed turn save does not fail the answer: AI-CHAT-13 audit, traces and log hygiene.
169. model and tool calls are traced with names and no content: AI-CHAT-13 Happy, each tool call traced with its latency.
170. chat code has no redaction violations: AI-CHAT-13 audit, traces and log hygiene.
171. the checker flags message answer and tool result fields: AI-CHAT-13 audit, traces and log hygiene.

--- test_deletion (4) ---
172. conversations usage and audit are handled for the deleted user: AI-CHAT-14 account deletion.
173. redelivery succeeds and changes nothing: AI-CHAT-14 Alt, re-delivery changes nothing.
174. a failed delete raises so the queue retries and nothing is published: AI-CHAT-14 Fail, a failed delete retries.
175. chat security events are anonymized with the other audit items: AI-CHAT-14 account deletion.

--- test_config (10) ---
176. the defaults are the appendix c values: AI-CHAT Appendix C defaults.
177. no allowance is invented for any tier: AI-CHAT-02 Appendix C, open question 3.
178. allowances come from config and an unknown tier gets the lowest: AI-CHAT-02 Appendix C, open question 3.
179. settings from json convert each value to its type: AI-CHAT Appendix C settings.
180. an unapproved model is rejected: AI-CHAT-15 model and cost controls.
181. the approved list is configurable: AI-CHAT-15 model and cost controls.
182. startup fails for a model id that is not approved: AI-CHAT-15 model and cost controls.
183. the env model overrides the default: AI-CHAT-15 model and cost controls.
184. invalid deployed settings fall back to the defaults that block chat: AI-CHAT Appendix C defaults.
185. the cost guard prices the chat model and shares the summary budget: AI-CHAT-15 model and cost controls.

--- test_store (7) ---
186. turns come back oldest first limited to the most recent: AI-CHAT-03 conversations.
187. a conversation is only visible to its owner: AI-CHAT-03 conversations.
188. creating a conversation twice keeps one record: AI-CHAT-03 conversations.
189. turns of one conversation do not mix with another: AI-CHAT-03 conversations.
190. saving a turn extends the conversation ttl to 30 days after it: AI-CHAT-03 conversations.
191. token usage accumulates per user and day: AI-CHAT-02 daily token usage.
192. the usage item expires with its day: AI-CHAT-02 daily token usage.

--- test_chat_clients (11) ---
193. category trends come from the internal section route: AI-CHAT-05 data tools.
194. top merchants take the period: AI-CHAT-05 data tools.
195. an analytics failure is a generic client error: AI-CHAT-05 data tools.
196. every internal call carries the context headers and the trace id: AI-CHAT-13 one trace_id across services.
197. search reads the internal route once and takes the totals from the ledger: AI-CHAT-05 / LG-READ-02.
198. search sends no parameter it was not given: AI-CHAT-05 / LG-READ-01.
199. search never returns more than 25 rows even if the ledger sends more: AI-CHAT-05 Alt, 25 rows plus totals.
200. a ledger failure is a generic client error: AI-CHAT-05 / LG-READ-04 Fail.
201. retrieve posts the query with scope system and no user: AI-CHAT-07 Knowledge retrieve contract.
202. every knowledge error is no docs available: AI-CHAT-07 Fail, every KN-RET error is no docs.
203. a malformed knowledge response is no docs available: AI-CHAT-07 Fail, every KN-RET error is no docs.
