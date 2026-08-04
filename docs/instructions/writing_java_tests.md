# Writing Good Tests in This Java Codebase
## Description
Good practices for writing tests in the Ledger service (Java/Spring Boot/jOOQ), covering the test pyramid, which Maven plugin runs which test type, how to write real Testcontainers integration tests without accidentally testing nothing, and how to write Fail-to-Pass (F2P) tests for requirements that don't have an implementation yet. Grounded in concrete examples already in this repo — `TransactionServiceTest.java` (unit) and `JooqTransactionRepositoryIT.java` (integration).

## Guideline

Step 1: Know the test pyramid and what each layer actually proves
Don't reach for the same kind of test for every question. Each layer answers a different question, at a different cost:

| Layer | What it proves | Speed | What it replaces with a test double |
|---|---|---|---|
| Unit test | Business logic/branching is correct — validation, state transitions, exception mapping | Milliseconds | Repository, external services — everything at the architectural seam |
| Integration test | The SQL, schema, constraints, transactions actually work | Seconds (container startup) | Nothing below the DB — real Postgres via Testcontainers |
| Contract/web-layer test (`@WebMvcTest`) | HTTP shapes, status codes, `@Valid` annotations fire correctly | Fast-ish | The service layer (mocked), real Spring MVC dispatch |
| End-to-end | Full user flow across real, wired-up services | Slow, brittle | Nothing |

Want many unit tests (cheap, run on every save), a much smaller set of integration/contract tests (targeted at genuine DB/HTTP-layer risk), and very few end-to-end tests. Don't invert this — an integration test for every branch a unit test could already cover just makes CI slow without adding confidence.

Step 2: Write unit tests with mocked collaborators, at the right seam
Mock at architectural boundaries — repository interfaces, other services — never internals (private methods, or deep mocking of a library's fluent API like jOOQ's `DSLContext`). See `TransactionServiceTest.java`: `TransactionRepository` and `StatementService` are mocked; the test verifies `TransactionServiceImpl`'s own decision-making (ownership checks, status-transition guards, split-amount math), not persistence.

A unit test with a mocked repository can only prove "the service correctly instructs the persistence layer to do X." It cannot prove the persistence layer actually does X against a real database — don't try to fake that confidence with a `verify(...)` call. That's what Step 4 is for.

Step 3: Separate fast and slow tests with Maven plugins
Two different plugins own two different naming conventions and lifecycle phases:
- **Surefire** runs `*Test.java` during `mvn test` — the fast unit-test loop, no external infrastructure.
- **Failsafe** runs `*IT.java` during `mvn verify` (bound to the `integration-test`/`verify` phases) — allowed to be slow, spin up Testcontainers, etc.

Add Failsafe alongside Surefire (already present via the Spring Boot parent POM):
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-failsafe-plugin</artifactId>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```
Name the test class `*IT.java` (not `*Test.java`) and it's automatically picked up by Failsafe and automatically skipped by Surefire — no extra config needed. Verify the split actually works: `mvn test` should never start Docker; `mvn org.apache.maven.plugins:maven-failsafe-plugin:integration-test` should.

Step 4: Write integration tests against a real database — and don't accidentally test nothing
Testcontainers' default Postgres bootstrap user is a **superuser**. Superusers unconditionally bypass Row Level Security, regardless of `FORCE ROW LEVEL SECURITY`. A test that runs entirely as that default user will "pass" an RLS test without RLS ever being enforced — a genuinely easy mistake with a database security feature you're trying to prove works.

The correct sequence (see `AbstractIntegrationTest.java`):
1. Start the container once, as a singleton shared across test classes (Testcontainers' documented pattern: start in a static initializer, never call `.stop()` — the Ryuk reaper cleans it up on JVM exit).
2. Run Flyway migrations as the superuser (DDL needs elevated privileges anyway).
3. Create a genuinely restricted, non-superuser role (`CREATE ROLE app_user LOGIN PASSWORD '...'`), and grant it only what the app needs (`GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ledger TO app_user`).
4. Point the Spring context's `spring.datasource.*` at that restricted role via `@DynamicPropertySource`, with `spring.flyway.enabled=false` (migrations already ran manually in step 2 — don't let Spring's own Flyway auto-configuration try to re-run them as a role with no DDL privileges).

For fixture setup (inserting rows the test needs), it's fine to use a raw JDBC connection as the superuser — that's fixture data, not the thing under test. Run your actual *assertions* through the real, Spring-managed, `app_user`-backed beans, so the code path under test matches what production actually does.

Step 5: Know the sharp edges of this exact stack (Postgres + jOOQ + Spring)
Two real bugs were found and fixed writing `JooqTransactionRepositoryIT`, both invisible to any mock-based test:
- **Postgres's `SET` command does not accept bind parameters.** `SET x = $1` is a syntax error — `SET` is a utility statement, not a parameterizable query. Use `SELECT set_config('x', ?, false)` instead (a regular function call, which does accept parameters). Relevant if you're setting session variables (e.g. for Row Level Security) from a jOOQ `ExecuteListener`.
- **Don't close a `Statement`/`ResultSet` derived from `ctx.connection()` inside a jOOQ `ExecuteListener`, outside an active Spring transaction.** Spring's `TransactionAwareDataSourceProxy` treats closing any resource derived from that connection as "done with it" and immediately returns the physical connection to the pool — leaving jOOQ's very next statement on that same connection object failing with "Connection is closed." Let the connection's own lifecycle (managed by jOOQ) handle cleanup instead of closing statements yourself in `start()`/`end()`-style listener callbacks.

Step 6: Writing Fail-to-Pass (F2P) tests for a requirement with no implementation yet
When a spec requirement has no corresponding method at all, you can't write a test against it without breaking compilation of the whole test file (Java compiles the whole file, not just the test you're adding). The pattern used for `TransactionServiceTest.java`'s `UpdateCategory`/`UpdateAmount`/`AppendTags` nested classes:
1. Add the minimal method signature to the interface (contract only).
2. Give it a stub implementation that throws `UnsupportedOperationException` — no real logic, so you don't accidentally guess at (and lock in) the wrong behavior.
3. Write tests describing the *intended* behavior — what should be true once someone implements it for real — focused on observable outcomes (what gets persisted, what exception is thrown for invalid input) rather than incidental implementation details.
4. Run the suite and confirm: every pre-existing test still passes, and exactly the new tests fail, for the expected reason (an `UnsupportedOperationException`/assertion mismatch, not a compile error).
5. Comment each test with which spec requirement it maps to, so "why does this fail" is self-explanatory to the next person who picks it up.
