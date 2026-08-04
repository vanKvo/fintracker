# Connect the Ledger to a Shared Local Postgres
## Description
The Ledger Service no longer defines its own dedicated Postgres container. Local dev often already runs one shared Postgres container serving multiple unrelated projects (multiple databases inside a single instance) rather than a separate Postgres container per project. This guide covers pointing the Ledger at that shared instance instead.

## Guideline
Step 1: Confirm a local Postgres is running and reachable on port 5432
```bash
docker run --name fintracker -e POSTGRES_PASSWORD=mysecretpassword -d -p 5432:5432 postgres

psql -h localhost -p 5432 -U postgres -c "SELECT version();"
```
If nothing is listening, start whatever shared Postgres container you use for local projects (this repo doesn't define or manage it — it's expected to already exist, e.g. a plain `docker run postgres` container used across multiple projects). It doesn't need to be Postgres 16 specifically for the Ledger's own SQL usage; version 16+ is fine.

Step 2: Create the `fintracker` database
The Ledger connects to a database named `fintracker`. Create it once inside your shared instance:
```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE fintracker;"
```
Safe to skip if it already exists — Flyway migrations run against whatever schema state is there on `mvn spring-boot:run`.

Step 3: Point `services/fintracker-ledger/.env` at it
```
DB_URL=jdbc:postgresql://localhost:5432/fintracker
DB_USERNAME=postgres
DB_PASSWORD=<your shared instance's postgres password>
```
This is what `mvn spring-boot:run` reads (via `application.yml`'s `${DB_URL}`/`${DB_USERNAME}`/`${DB_PASSWORD}`). No Docker involved for this path — Maven runs natively on the host, so `localhost:5432` reaches whatever Postgres is bound to that port.

Step 4: If running the Ledger itself in a container instead of via Maven
`services/fintracker-ledger/docker-compose.yml`'s `ledger` service already points at `host.docker.internal:5432` — Docker Desktop's DNS name for the host machine — so it reaches the same shared Postgres without needing to be on the same Docker network:
```bash
cd services/fintracker-ledger
docker compose up -d
```

Step 5: Run the Ledger and verify
```bash
mvn spring-boot:run
```
Flyway should apply migrations against the `fintracker` database on startup with no connection errors.
