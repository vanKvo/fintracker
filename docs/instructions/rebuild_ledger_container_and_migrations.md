# Rebuild the Ledger container after a code change (with database migrations)

## Description
Run this every time you change the Ledger's code, its `pom.xml`, or its Dockerfile, and you want the
containerized Ledger (port 8081) to run the new code. Flyway applies any new migration in
`src/main/resources/db/migration` on startup, so this one command also migrates the shared `fintracker`
database. Data-only changes are not covered here; see step 4.

## Guideline
Step 1: Make sure the shared Postgres is running and reachable on port 5432
See [connect_ledger_to_shared_postgres.md](connect_ledger_to_shared_postgres.md). The container reaches it at `host.docker.internal:5432`.

Step 2: Rebuild the image and recreate the container
```bash
cd services/fintracker-ledger
docker compose up -d --build ledger
```
Running `docker compose up -d --build ledger` from the repo root also works, because the root
`docker-compose.yml` includes this file under the same project name (`fintracker`). Use one or the other, not both.

Step 3: Watch startup and confirm the migrations applied
```bash
docker compose logs -f ledger
```
Look for Flyway's `Successfully applied N migration(s)` line (or `Schema ... is up to date`). A failed migration
stops startup and the container exits. Fix the SQL, then repeat step 2.

Verify the migration history and the service:
```bash
psql -h localhost -U postgres -d fintracker -c \
  "select installed_rank, version, description, success from ledger.flyway_schema_history order by installed_rank desc limit 5;"

curl -s http://localhost:8081/actuator/health
```
Every row shown should have `success = t`, and health should report `UP`.

Step 4: Run any one-time data script that goes with this change
Data backfills are not Flyway migrations. They live in `services/fintracker-ledger/scripts/one-time/`, and
each file's header says when to run it (often right after a specific migration) and as which role. Run them
by hand with `psql`, as the Postgres superuser, which bypasses RLS:
```bash
psql -h localhost -U postgres -d fintracker -f services/fintracker-ledger/scripts/one-time/<file>.sql
```

## Notes
- Do not use `docker compose down -v` for this. The rebuild does not need it, and it removes volumes.
- A `success = f` row in `flyway_schema_history` makes Flyway refuse to continue. Do not edit an applied
  migration file, because Flyway checksums it. Ask before repairing the history table.
- Migrations run inside the container's startup, so they apply even if the service later fails to start
  for an unrelated reason (for example, a missing bean or configuration value). Check the log for both.
