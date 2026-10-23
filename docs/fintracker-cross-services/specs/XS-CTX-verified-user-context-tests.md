=========================
F2P TESTS (111)
=========================

--- user-profile · test_settings_validation (4) ---
1. accepts iana timezone names: XS-CTX-01, Appendix A.
2. rejects anything that is not an iana timezone name: XS-CTX-01 Fail.
3. accepts usd as the only supported currency: XS-CTX-01, Appendix A.
4. rejects unsupported currencies: XS-CTX-01 Fail.

--- user-profile · TestRegistrationSettings (1) ---
5. new user gets usd and no timezone: XS-CTX-01.

--- user-profile · TestSaveSettings (3) ---
6. valid timezone is saved and the stored settings returned: XS-CTX-01 Happy.
7. invalid values store nothing: XS-CTX-01 Fail, XS-CTX-06 Fail.
8. unknown user is not found: XS-CTX-01.

--- user-profile · TestProfileAndSettingsInOneRead (2) ---
9. profile and settings come from one repository read: XS-CTX-02 Happy.
10. either item missing is not found: XS-CTX-02.

--- user-profile · TestUpdateSettingsHandler (5) ---
11. saves the browser timezone: XS-CTX-01 Happy.
12. invalid setting is 400 invalid_setting with generic text: XS-CTX-01 Fail, Appendix C.
13. malformed body is 400 and stores nothing: XS-CTX-01 Fail.
14. unknown fields are ignored and not stored: XS-CTX-01.
15. unknown user is 404 without internal detail: XS-CTX-01.

--- user-profile · TestGetProfileSettingsShape (1) ---
16. missing timezone is null, not a default: XS-CTX-01, XS-CTX-05 Fail.

--- user-profile · TestStoredSettings (4) ---
17. user registered without a timezone reads back none, not a default: XS-CTX-01, XS-CTX-05 Fail.
18. item without a currency reads back none, not usd: XS-CTX-05 Fail.
19. update changes only the given fields: XS-CTX-01, XS-CTX-06.
20. update for a user without settings is not found and creates nothing: XS-CTX-01 Fail.

--- user-profile · TestOneQueryForProfileAndSettings (2) ---
21. profile and settings come from a single query and no get_item: XS-CTX-02 Happy.
22. missing items come back as none: XS-CTX-02.

--- user-profile · TestReqUp02ContextInjection (1) ---
23. allow response carries internal_user_id, subscription_tier, timezone and currency: XS-CTX-02 Happy.

--- user-profile · TestXsCtx02TimezoneAndCurrencyInContext (4) ---
24. context carries all four fields: XS-CTX-02 Happy.
25. one service read per uncached request: XS-CTX-02 Happy.
26. user without a timezone is still allowed with an empty value: XS-CTX-02 Alt.
27. missing currency is passed on empty, not defaulted: XS-CTX-02, XS-CTX-05 Fail.

--- user-profile · test_backfill_user_settings (4) ---
28. sets both values for the given user: XS-CTX-01 Alt.
29. refuses to run without a timezone: XS-CTX-01 Alt.
30. refuses an invalid timezone: XS-CTX-01 Alt.
31. does not create settings for an unknown user: XS-CTX-01 Alt.

--- user-profile · test_settings_route_config (3) ---
32. put /profile/settings route exists behind the authorizer: XS-CTX-01, XS-CTX-06.
33. authorizer cache ttl is at most five minutes: XS-CTX-06 Alt.
34. no internal settings route is declared: XS-CTX-07 Happy.

--- analytics · test_user_context (16) ---
35. reads timezone and currency from the authorizer context: XS-CTX-02, XS-CTX-05 Happy.
36. missing timezone is 409 user_settings_incomplete: XS-CTX-05, Appendix C.
37. invalid timezone is 500 user_context_invalid: XS-CTX-05 Fail, Appendix C.
38. missing or unsupported currency is 500 user_context_invalid: XS-CTX-05 Fail, Appendix C.
39. no authorizer context never yields a default: XS-CTX-05 Fail.
40. an invalid value raises the metric and an error log: XS-CTX-05 Fail.
41. a missing timezone does not raise the alarm: XS-CTX-05 Alt.
42. local dev values are used only when app_env is local: XS-CTX-05.
43. local dev without the variables has no default: XS-CTX-05 Fail.
44. client-sent settings headers never override the authorizer: XS-CTX-03, XS-CTX-05.
45. client-sent headers do not fill a missing authorizer timezone: XS-CTX-03, XS-CTX-05.
46. invalid currency in context is 500 and no work starts: XS-CTX-05 Fail.
47. internal route reads forwarded headers after the caller check: XS-CTX-04 Happy.
48. internal route without forwarded timezone is 409: XS-CTX-05.
49. headers from a role off the allow-list are ignored and rejected with 403: XS-CTX-04 Fail.
50. public request cannot supply settings through internal headers: XS-CTX-04, XS-CTX-03.

--- analytics · test_internal_routes (3) ---
51. no iam identity is 401 and nothing runs: XS-CTX-04.
52. verified caller not on the allow-list is 403 and nothing runs: XS-CTX-04 Fail.
53. unset allow-list fails closed with 403: XS-CTX-04 Fail.

--- analytics · test_periods (1) ---
54. unknown timezone is an error, not utc: XS-CTX-05 Fail.

--- analytics · test_service (1) ---
55. period follows the verified timezone and currency reaches the loader: XS-CTX-05 Happy.

--- analytics · test_router (2) ---
56. public facts and periods use the authorizer user and settings: XS-CTX-02, XS-CTX-05 Happy.
57. internal facts use the forwarded user and settings: XS-CTX-04 Happy.

--- ai-assistant · test_user_context (10) ---
58. reads user, timezone and currency from the authorizer context: XS-CTX-02, XS-CTX-04.
59. the three forwarded headers carry the same values: XS-CTX-04 Happy.
60. missing timezone is 409 user_settings_incomplete: XS-CTX-05, Appendix C.
61. invalid timezone is 500 user_context_invalid: XS-CTX-05 Fail.
62. missing or unsupported currency is 500 user_context_invalid: XS-CTX-05 Fail.
63. no user in the context is 401: XS-CTX-05.
64. an invalid value raises the metric and an error log: XS-CTX-05 Fail.
65. local dev values apply only when app_env is local: XS-CTX-05.
66. local dev without timezone or currency has no default: XS-CTX-05 Fail.
67. summary route answers 409 with a code and request id when the timezone is missing: XS-CTX-05 Alt.

--- ai-assistant · test_execute_tool (5) ---
68. a valid call runs the tool with the bound context: XS-CTX-04 Happy.
69. context arguments are rejected before any call and logged as a security event: XS-CTX-04 Fail.
70. any other unexpected argument is rejected too: XS-CTX-04 Fail.
71. an unknown tool is rejected: XS-CTX-04 Fail.
72. the rejection message is generic: XS-CTX-04 Fail.

--- ai-assistant · test_tools (1) ---
73. no tool accepts a user, timezone or currency parameter: XS-CTX-04 Fail.

--- ai-assistant · TestForwardedUserContext (1) ---
74. analytics and ledger calls carry the three context headers on a signed request: XS-CTX-04 Happy.

--- ai-assistant · test_facts_client (2) ---
75. signed facts call carries the user, timezone and currency: XS-CTX-04 Happy.
76. analytics asking for a timezone is surfaced, not hidden as unavailable: XS-CTX-05 Alt.

--- ai-assistant · test_router (2) ---
77. summary routes pass the authorizer context to the service: XS-CTX-02, XS-CTX-04.
78. refresh passes the authorizer context to the service: XS-CTX-02, XS-CTX-04.

--- ledger · UserSettingsTest (5) ---
79. a valid iana timezone and usd are accepted as given: XS-CTX-05 Happy.
80. a missing timezone is settings incomplete, never utc: XS-CTX-05 Fail.
81. a timezone that is not an iana name is an invalid user context: XS-CTX-05 Fail.
82. a missing or unsupported currency is an invalid user context, never usd: XS-CTX-05 Fail.
83. an invalid exception never carries the rejected value: XS-CTX-05, Appendix C.

--- ledger · DashboardUserContextIT (7) ---
84. the month shown follows the user's timezone: new york is still in july: XS-CTX-05 Happy.
85. the month shown follows the user's timezone: tokyo is already in august: XS-CTX-05 Happy.
86. without a timezone the dashboard answers 409 user_settings_incomplete: XS-CTX-05, Appendix C.
87. an empty timezone is the same as a missing one: XS-CTX-05.
88. an invalid timezone is 500 user_context_invalid and counts on the alarm metric: XS-CTX-05 Fail.
89. an empty or unsupported currency is 500 user_context_invalid, never usd: XS-CTX-05 Fail.
90. the error body is generic and never echoes the rejected value: XS-CTX-05, Appendix C.

--- ui · timezone helpers (3) ---
91. accepts iana names: XS-CTX-01.
92. rejects values that are not iana names: XS-CTX-01 Fail.
93. offers a sorted list of valid names with no default chosen: XS-CTX-01 Alt.

--- ui · ProfileService settings (2) ---
94. puts only the timezone to /profile/settings: XS-CTX-01, XS-CTX-06.
95. caches the profile settings for the dev gateway headers until a save: XS-CTX-03.

--- ui · TimezoneSetupService (6) ---
96. does nothing when the profile already has a timezone: XS-CTX-01.
97. first app load saves the browser timezone and then completes: XS-CTX-01 Happy.
98. shows the picker, with nothing preselected, when the browser reports none or an invalid zone: XS-CTX-01 Alt.
99. shows the picker when saving the browser timezone is refused: XS-CTX-01 Alt.
100. never blocks the app when the profile cannot be loaded: XS-CTX-01.
101. asks only once when several requests need the picker at the same time: XS-CTX-05 Alt.

--- ui · settingsIncompleteInterceptor (3) ---
102. shows the picker and retries the request once the timezone is saved: XS-CTX-05 Alt.
103. does not loop on a second 409: XS-CTX-05 Alt.
104. leaves other errors alone: XS-CTX-05.

--- ui · authInterceptor (local dev, ledger) (2) ---
105. sends the saved timezone and currency with every ledger request: XS-CTX-03 Happy.
106. leaves the timezone header out when the user has none: XS-CTX-03, XS-CTX-05.

--- ui · Settings page (5) ---
107. shows the saved timezone and a read-only usd currency: XS-CTX-01 Currency.
108. leaves the timezone empty, not defaulted, when none is saved yet: XS-CTX-01.
109. saves a changed timezone and says it can take up to 5 minutes to apply: XS-CTX-06 Happy.
110. keeps the previous timezone when the save is refused: XS-CTX-06 Fail.
111. does not call the server when the timezone did not change: XS-CTX-06.
