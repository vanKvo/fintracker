# Bug name: Ledger container fails to start / fails to sign S3 uploads in local Docker dev

## Problem
Running the Ledger Service via `docker compose up` failed with `UnsatisfiedDependencyException` cascading from `budgetController` down to `s3PresignService`, ultimately caused by:
```
software.amazon.awssdk.core.exception.SdkClientException: Unable to load credentials from any of the providers in the chain AwsCredentialsProviderChain(...)
```
Separately, before that, the same container failed to boot at all with `PlaceholderResolutionException: Could not resolve placeholder 'AWS_REGION'`.

### Root cause:
Two compounding issues:
1. `services/fintracker-ledger/docker-compose.yml` never set `AWS_REGION`, and `aws.region: ${AWS_REGION}` in `application.yml` has no fallback in any profile — the container had no region to construct any AWS SDK client with.
2. `S3PresignService` unconditionally built its `S3Presigner` with the AWS SDK's **default credentials provider chain** (env vars → profile file → container/instance-profile credentials), which is correct for real deployments (an IAM role) but has nothing to resolve against in local Docker dev — no `~/.aws/credentials` is mounted into the container, and there was no local S3 emulator (LocalStack) running for it to point at in the first place. There was also no way to point the client at a local endpoint at all — `endpointOverride` was never wired up.

A secondary bug surfaced while fixing this: `STATEMENTS_BUCKET_NAME=statement_bucket_dev` in `.env` uses underscores, which is not a valid S3 bucket name (S3 only allows lowercase letters, digits, and hyphens) — this would have failed against real AWS too, not just LocalStack.

### Code with bug:
```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/service/S3PresignService.java
public S3PresignService(
        @Value("${aws.s3.statements-bucket}") String bucketName,
        @Value("${aws.s3.presigned-url-expiry-minutes}") long expiryMinutes,
        @Value("${aws.region}") String region
) {
    this.bucketName = bucketName;
    this.expiry = Duration.ofMinutes(expiryMinutes);
    this.presigner = S3Presigner.builder()
            .region(software.amazon.awssdk.regions.Region.of(region))
            .build();
}
```
```yaml
# services/fintracker-ledger/docker-compose.yml
environment:
  DB_URL: jdbc:postgresql://host.docker.internal:5432/fintracker
  DB_USERNAME: postgres
  DB_PASSWORD: mysecretpassword
```

## Solution
Introduced a local S3 emulator (LocalStack, Community edition) as the repo's established pattern already does for DynamoDB (`setup_local_dynamodb.md`), and made `S3PresignService` able to point at it via an optional endpoint override — while leaving real-deployment behavior (default credentials chain, no override) completely unchanged.

1. Added `AWS_REGION: us-east-1` to `docker-compose.yml`, matching `.env`.
2. Added a `localstack` service to the root `docker-compose.yml` (pinned to `localstack/localstack:3.8`, a Community-edition tag — `:latest` currently requires a paid license token and refuses to start without one).
3. Added `aws.s3.endpoint-override: ${AWS_S3_ENDPOINT_OVERRIDE:}` to `application.yml` (empty default — unset in every real deployment).
4. `S3PresignService` now conditionally applies `endpointOverride` + a `StaticCredentialsProvider` (LocalStack's documented `test`/`test` placeholder, never valid against real AWS) only when that property is non-blank.
5. Set `AWS_S3_ENDPOINT_OVERRIDE` to `http://host.docker.internal:4566` in `docker-compose.yml` (containerized path) and `http://localhost:4566` in `.env` (host `mvn spring-boot:run` path).
6. Fixed `STATEMENTS_BUCKET_NAME` from `statement_bucket_dev` to `statement-bucket-dev` in both `.env` and `docker-compose.yml`.
7. Documented the setup in `docs/instructions/setup_local_s3.md` (start container → verify → create bucket → point service at it → verify → teardown), mirroring `setup_local_dynamodb.md`.

Verified end-to-end: `docker compose up -d localstack`, created the `statement-bucket-dev` bucket via `aws s3 mb --endpoint-url http://localhost:4566`, rebuilt and started the ledger container — it now logs `Started LedgerServiceApplication` with no exception (previously failed at `s3PresignService` bean creation).

### Fixed Code
```java
// services/fintracker-ledger/src/main/java/com/fintracker/ledger/statement/service/S3PresignService.java
public S3PresignService(
        @Value("${aws.s3.statements-bucket}") String bucketName,
        @Value("${aws.s3.presigned-url-expiry-minutes}") long expiryMinutes,
        @Value("${aws.region}") String region,
        @Value("${aws.s3.endpoint-override:}") String endpointOverride
) {
    this.bucketName = bucketName;
    this.expiry = Duration.ofMinutes(expiryMinutes);
    var builder = S3Presigner.builder()
            .region(software.amazon.awssdk.regions.Region.of(region));
    if (!endpointOverride.isBlank()) {
        builder.endpointOverride(URI.create(endpointOverride))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create("test", "test")));
    }
    this.presigner = builder.build();
}
```
```yaml
# services/fintracker-ledger/docker-compose.yml
environment:
  SPRING_PROFILES_ACTIVE: dev
  DB_URL: jdbc:postgresql://host.docker.internal:5432/fintracker
  DB_USERNAME: postgres
  DB_PASSWORD: mysecretpassword
  AWS_REGION: us-east-1
  AWS_S3_ENDPOINT_OVERRIDE: http://host.docker.internal:4566
  STATEMENTS_BUCKET_NAME: statement-bucket-dev
```
