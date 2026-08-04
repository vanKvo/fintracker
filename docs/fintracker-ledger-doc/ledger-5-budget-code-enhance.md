Fixed
- Contract drift: closePastBudgets(null) now throws NullPointerException via Objects.requireNonNull (a system-caller programming error, not a client 4xx), and the interface declares @throws NullPointerException plus the cutoff-normalization behavior (BudgetService.java:79).
- Atomicity: JooqBudgetRepository.save (header + lines) and updateLines (delete + reinsert + version bump) now run inside dsl.transaction(...) — previously a mid-write failure could leave a half-written budget or silently drop all existing lines.
- N inserts → 1 batch: saveLines uses ctx.batch(...) (one round-trip for up to 50 lines).
- Duplication: extracted cloneLines(...) helper (was copy-pasted in template seeding and previous-budget cloning).
- Input hygiene: payload categories are strip()ped before persistence, consistent with the duplicate-detection normalization.
Reviewed and deliberately left as-is
- Per-line spend enrichment is an N+1 against sumMonthlyExpensesPerCategory; acceptable at ≤50 lines and the only aggregation TransactionService exposes — a grouped-by-category repository query would be the next optimization.
- No @Transactional at the service layer — the codebase uses repository-level transactions only (matches closeAllBefore); introducing spring-tx annotations service-wide would be a broader convention change.
- InvalidBudgetException for null userId/month on user-facing methods stays: those map to the documented 400 contract.
- Scheduler exceptions are already logged by Spring's default @Scheduled error handler; an extra try/catch would be redundant.