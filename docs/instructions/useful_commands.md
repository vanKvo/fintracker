## Run unit and integration tests (faster compilation phase if jOOQ generation is skipped, but runs full integration tests) and output the result to a log
cd services/fintracker-ledger
mvn verify -DskipITs=false -DskipJooq=true | tee /tmp/verify.log
grep -m3 -A8 "ERROR.*Tests run" /tmp/verify.log

## Rebuild container and run it
docker compose up -d --build ledger

## Check "Did I run what I've just built?"
// The exact timestamp when the fintracker-ledger Docker image was built.
docker image inspect fintracker-ledger --format '{{.Created}}'

// Lists the compiled Java class files (.class) inside the active container's controller package directory.
docker exec fintracker-ledger-1 ls /app/BOOT-INF/classes/com/fintracker/ledger/statement/controller/

## Check which profile is active in a container
docker exec <container> env | grep SPRING_PROFILES_ACTIVE   # container path only