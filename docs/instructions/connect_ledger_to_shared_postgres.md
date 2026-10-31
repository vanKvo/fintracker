# Connect the Ledger to the Shared Local PostgreSQL Container

## Description
The Ledger does not define its own Postgres. It uses the shared PostgreSQL container defined in `infrastructure/local-postgres/`
(container `fintracker-postgres`, image `pgvector/pgvector:pg17`, named volume `fintracker-pg-data`). The Knowledge service uses the
same container, with its own `knowledge` database. This guide covers starting that container and pointing the Ledger at it.

## Guideline
Step 1: Start the shared container (once)
```bash
cd infrastructure/local-postgres
cp .env.example .env          # first time only; set POSTGRES_PASSWORD (use mysecretpassword: the Ledger's compose file uses it)
docker compose up -d
docker inspect -f '{{.State.Health.Status}}' fintracker-postgres   # should print: healthy
```
The first start creates the `fintracker` database (for the Ledger), the `knowledge` database and Knowledge's login roles.
It does not run again on later starts: the data lives in the `fintracker-pg-data` volume and survives `docker compose down`.
Do not use `docker compose down -v` or `docker volume rm fintracker-pg-data`: those delete all data.

Step 2: Confirm the server answers on port 5432
```bash
docker exec fintracker-postgres psql -U postgres -d fintracker -Atc "SELECT count(*) FROM ledger.accounts"
```
Port 5432 must be used by this container only. Stop any other Postgres on that port first (see `setup_postgresql16_homebrew.md`).

Step 3: Point `services/fintracker-ledger/.env` at it (for `mvn spring-boot:run`)
```
DB_URL=jdbc:postgresql://localhost:5432/fintracker
DB_USERNAME=postgres
DB_PASSWORD=mysecretpassword
```
Maven runs on the host, so `localhost:5432` reaches the container's published port.

Step 4: Run the Ledger in a container instead of via Maven (optional)
`services/fintracker-ledger/docker-compose.yml`'s `ledger` service connects to `host.docker.internal:5432`, which reaches the same container:
```bash
cd services/fintracker-ledger
docker compose up -d
```

Step 5: Run the Ledger and verify
```bash
mvn spring-boot:run
```
Flyway applies any pending migrations to the `fintracker` database on startup with no connection errors.
