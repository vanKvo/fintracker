Whether it's fetched variables from the .env file depends entirely on how you run the service — the profile rename doesn't change this:

mvn spring-boot:run (host, no container): yes. spring.config.import: "optional:file:.env[.properties]" (application.yml:4-5) resolves relative to the process's working directory, which is services/fintracker-ledger/ when you run Maven from there — so it picks up the real .env (dev DB creds, statement_bucket_dev, etc.).
docker compose up -d (container): no. The Dockerfile overwrites .env with dummy placeholders (DB_URL=unused, etc.) during the build stage purely to satisfy the Maven build, and only the compiled/extracted JAR layers get copied into the runtime image (no .env file at all). So a containerized run gets zero values from .env — everything must come from the environment: block in docker-compose.yml, which is why DB_URL/DB_USERNAME/DB_PASSWORD are hardcoded there, and why SPRING_PROFILES_ACTIVE: dev needed to be added explicitly for the caller-ARN and bucket-name fallbacks to kick in.
How to verify at runtime, either path:


curl -s localhost:8081/actuator/info | jq   # 'info' is exposed; won't show profile by default though
docker exec <container> env | grep SPRING_PROFILES_ACTIVE   # container path only
info/health/metrics/prometheus are the only actuator endpoints exposed (application.yml:47-51) — env isn't, so docker exec ... env (or checking your shell's exported vars for the Maven path) is the reliable way to confirm which profile/values are actually in effect.