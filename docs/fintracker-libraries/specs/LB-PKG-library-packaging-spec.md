# LB-PKG: Library Packaging, Versioning and Adoption

| Field | Value |
|---|---|
| Product | FinTracker |
| Prefix | LB-PKG |
| File | fintracker-libraries/specs/LB-PKG-library-packaging-spec.md |
| Owner | Van Vo |
| Status | Draft |
| Last updated | 2026-10-30 |

---

## 1. Overview

### Problem
Shared Python code (the internal HTTP library in LB-IHTTP, a log redaction library next) is only useful if services can take a change without copying it, and without one change breaking every service at once. Without rules for versions, releases and upgrades, a shared library becomes a hidden coupling: services drift to old copies again, a breaking change lands unannounced, or a security fix sits in one service for months.

### Goals
- Every shared library is a versioned package with the same layout, the same release steps and the same upgrade path.
- A service chooses when to move to a new version, and an upgrade is a one-line change that CI proves safe.
- A breaking change is visible in the version number and announced one release ahead.
- A security fix reaches every service within 7 days, and a report shows any service that is behind.
- Adding a new library means copying a layout, not inventing a process.

### Non-Goals
- Java libraries. Ledger is held to the same contract through shared test vectors (LB-IHTTP-10), not through a package.
- Frontend packages.
- Publishing outside FinTracker. All packages are private.
- Backporting fixes to old versions beyond the support window in LB-PKG-08.

### Design Principles
1. **Versions are immutable.** A published version is never changed or deleted. A mistake is fixed by a new version.
2. **Services pin exactly.** A service always knows which library version it runs. Libraries never decide for a service.
3. **The version number is the contract.** Patch means safe, minor means additive, major means a service must change something.
4. **Automation proposes, tests decide.** Upgrade pull requests are opened by a bot and merged only when the service's own tests pass.
5. **Small and boring.** Few dependencies, no runtime magic, one way to do each thing.

---

## 2. Workflow

```
[Create a library from the layout] ──► LB-PKG-01
    │
[Change it, record the change] ──► LB-PKG-02, LB-PKG-03
    │
[Release: tag, test, publish] ──► LB-PKG-04
    │
[Services get the release]
    ├─ pin exactly ──► LB-PKG-05
    └─ bot opens the upgrade PR ──► LB-PKG-06
    │
[Keep it healthy]
    ├─ report who is behind ──► LB-PKG-07
    └─ security fixes, old majors, bad releases ──► LB-PKG-08
    │
[Dependencies stay small] ──► LB-PKG-09
```

---

## 3. Requirements Index

| ID | Title | Area | Priority | Status |
|---|---|---|---|---|
| LB-PKG-01 | Every library follows one layout | Quality | MVP | Proposed |
| LB-PKG-02 | Versions follow semantic versioning with a defined public API | Quality | MVP | Proposed |
| LB-PKG-03 | Every change is recorded and removals are announced first | Quality | MVP | Proposed |
| LB-PKG-04 | A release is made by a tag and is immutable | Reliability | MVP | Proposed |
| LB-PKG-05 | Services pin exact versions | Reliability | MVP | Proposed |
| LB-PKG-06 | Upgrades are proposed by a bot and proved by service tests | Quality | MVP | Proposed |
| LB-PKG-07 | A report shows which service runs which version | Quality | MVP | Proposed |
| LB-PKG-08 | Security fixes, old majors and bad releases have a fixed procedure | Security | MVP | Proposed |
| LB-PKG-09 | Libraries keep few, loosely pinned dependencies | Quality | MVP | Proposed |

---

## 4. Requirements

### LB-PKG-01: Every library follows one layout  `Priority: MVP`

**Requirement:** A library lives in `libs/<name>/` in the root repository. The distribution name is `fintracker-<name>` and the import name is `fintracker_<name>`. The folder holds `pyproject.toml`, `README.md`, `CHANGELOG.md`, `src/<import name>/` (with `py.typed` and an `__init__.py` that defines `__all__`), and `tests/`. The version is set in one place, `pyproject.toml`. Supported Python versions are the runtime the services use now (3.13) and the previous minor (3.12).
**Acceptance Criteria:**
- [Happy] `pip install ./libs/<name>` in a clean virtual environment succeeds and `import fintracker_<name>` works.
- [Happy] The package's tests pass on 3.12 and 3.13 in CI.
- [Alt] `fintracker_<name>.__version__` equals the version in `pyproject.toml`.
- [Fail] A repository check fails when a library is missing any file listed above, has no `__all__`, or sets its version in a second place.
- [Fail] CI fails when type checking (`py.typed` present) reports errors in the public API.
**Refs:** Appendix A

### LB-PKG-02: Versions follow semantic versioning with a defined public API  `Priority: MVP`

**Requirement:** Versions are `MAJOR.MINOR.PATCH`. The public API is exactly the names in `__all__`, their signatures, their documented behavior and the settings and environment variables the README lists. Anything else is internal and may change in any release. A change that makes a previously valid call fail or behave differently is a major change. Added names, optional parameters and new settings with unchanged defaults are minor. Fixes that change no documented behavior are patch. A library starts at `1.0.0` when two services use it; before that it is `0.x`, and a `0.x` minor may break.
**Acceptance Criteria:**
- [Happy] A new optional parameter with a default is released as a minor version.
- [Alt] Changing a default value of a documented setting is released as a major version.
- [Alt] A change inside a name that is not in `__all__` can ship as a patch.
- [Fail] A pull request that removes or renames a name in `__all__`, or changes a public signature, fails CI unless the version in `pyproject.toml` is a new major and the changelog says so (checked by an API-diff step).
- [Fail] A tag whose version does not follow `MAJOR.MINOR.PATCH` is rejected by the release job.
**Refs:** Appendix B

### LB-PKG-03: Every change is recorded and removals are announced first  `Priority: MVP`

**Requirement:** `CHANGELOG.md` follows one format: a section per version, newest first, with headings Added, Changed, Deprecated, Removed, Fixed and Security, and the date. Every pull request that changes the library adds a line under an `Unreleased` section. A public name is never removed in the release where it is first deprecated: it is deprecated in a minor release (emitting `DeprecationWarning` with the replacement and the version it will go) and removed no earlier than the next major release.
**Acceptance Criteria:**
- [Happy] A release's changelog section lists every pull request merged since the last release.
- [Alt] Calling a deprecated name works and emits one `DeprecationWarning` naming the replacement.
- [Fail] CI fails a pull request that changes `src/` without a changelog line.
- [Fail] CI fails a major release that removes a name which was not deprecated in an earlier release.
- [Fail] The release job fails when the changelog has no section for the tagged version.
**Refs:** Appendix C

### LB-PKG-04: A release is made by a tag and is immutable  `Priority: MVP`

**Requirement:** A release is a git tag `<distribution name>-v<version>`, for example `fintracker-internal-http-v1.2.0`. The release job checks that the tag matches `pyproject.toml` and the changelog, runs the tests on both Python versions, builds the wheel and the source archive, and publishes them to the private package repository (AWS CodeArtifact, `fintracker-libs`, created in Terraform). The repository refuses to overwrite an existing version. The job posts the changelog section as the release notes.
**Acceptance Criteria:**
- [Happy] Pushing `fintracker-internal-http-v1.2.0` publishes version 1.2.0, and `pip install fintracker-internal-http==1.2.0` from the repository works.
- [Alt] A tag for one library does not build or publish any other library.
- [Fail] A tag that does not match `pyproject.toml` fails the job and publishes nothing.
- [Fail] If any test fails, nothing is published.
- [Fail] Publishing a version that already exists is refused by the repository and the job fails; the existing files are unchanged.
**Open Questions:** Registry or git install (consolidated question 1).
**Refs:** ADR-008 (Terraform layout)

### LB-PKG-05: Services pin exact versions  `Priority: MVP`

**Requirement:** A service lists each FinTracker library with an exact version (`fintracker-internal-http==1.2.0`) in its dependency file, and its Docker or Lambda build installs from the private repository using the exact pin. A hash-checked lock file is used where the service already has one. Service code imports only names in the library's `__all__`. A new library is adopted by a service in its own pull request that also deletes the service's copy of that logic.
**Acceptance Criteria:**
- [Happy] A service build installs exactly the pinned version, and the version appears in the build log.
- [Happy] A running service reports its library versions at startup in one log line (`libs={"fintracker-internal-http": "1.2.0"}`).
- [Alt] Two services may pin different versions of the same library at the same time.
- [Fail] A dependency file with a range (`>=`, `~=`, `*`) for a FinTracker library fails the repository check.
- [Fail] A service build that cannot reach the repository fails; it never falls back to a local copy or to the newest version.
- [Fail] A service that imports a name outside `__all__` fails the service's lint step.
**Refs:** LB-IHTTP-09

### LB-PKG-06: Upgrades are proposed by a bot and proved by service tests  `Priority: MVP`

**Requirement:** Renovate (or Dependabot) is configured on the repositories that hold services. It opens one pull request per library upgrade. Patch upgrades merge automatically when the service's CI is green. Minor upgrades open a pull request that needs a person to merge. Major upgrades open a pull request labelled `breaking` that lists the changelog's Changed and Removed items. Every library bump pull request runs the service's full tests and, where the library has one, its conformance suite.
**Acceptance Criteria:**
- [Happy] Releasing 1.2.1 results in an upgrade pull request in each service within 24 hours, merged when CI passes.
- [Alt] Releasing 1.3.0 opens a pull request that waits for review.
- [Alt] Releasing 2.0.0 opens a pull request with the `breaking` label and the changelog items in its description.
- [Fail] A bump whose CI fails is not merged and the bot keeps the pull request open.
- [Fail] The bot never opens a pull request that changes a service's own dependencies beyond the FinTracker libraries unless configured to.
**Refs:** Appendix D

### LB-PKG-07: A report shows which service runs which version  `Priority: MVP`

**Requirement:** A script, `libs/scripts/version_report.py`, reads each service's pins and the latest released version of each library, and prints a table: library, latest, and per service the pinned version and how far behind it is (patch, minor, major). It runs weekly and on every library release, and writes the table to `docs/fintracker-libraries/versions.md`. It exits non-zero when a service is a major version behind, or has not adopted a release marked security within 14 days.
**Acceptance Criteria:**
- [Happy] With all services on the latest version, every cell shows the version and the script exits 0.
- [Alt] A service one minor behind shows `1.1.0 (1 minor behind)` and the script exits 0.
- [Alt] A library no service uses yet appears in the table with no pins.
- [Fail] A service on 1.x when 2.0.0 is out makes the script exit non-zero and names the service and library.
- [Fail] A security release older than 14 days that a service has not adopted makes the script exit non-zero.
**Refs:** LB-PKG-08

### LB-PKG-08: Security fixes, old majors and bad releases have a fixed procedure  `Priority: MVP`

**Requirement:** A security fix is released as a patch on the latest version, marked `Security` in the changelog, and services adopt it within 7 days. Only the latest major version receives fixes; the previous major gets security fixes only for 90 days after a new major is released. A release found to be broken is never deleted. It is marked yanked in the changelog (with the reason and the fixed version), the repository's version is marked deprecated, and a fixed release is published; the report (LB-PKG-07) flags services pinned to a yanked version.
**Acceptance Criteria:**
- [Happy] A security patch released today appears in the report as "security, due in 7 days" for every service not on it.
- [Alt] A security fix needed on the previous major within 90 days is released as a patch on that major's branch with its own tag.
- [Fail] Trying to delete a published version is refused (repository policy) and the procedure to yank is followed instead.
- [Fail] A service pinned to a yanked version makes the report exit non-zero until it moves.
**Refs:** LB-PKG-04, LB-PKG-07

### LB-PKG-09: Libraries keep few, loosely pinned dependencies  `Priority: MVP`

**Requirement:** A library lists its runtime dependencies in `pyproject.toml` with a lower bound and an upper major bound (for example `httpx>=0.27,<1`), never an exact pin, so a service's own lock file decides. A library does not depend on another FinTracker library except one named in its README, and never on a service. Libraries do not import AWS SDK clients they do not need: a library that only signs requests depends on `botocore`, not `boto3`. Heavy or optional dependencies are optional extras. A new runtime dependency is a minor change and must be named in the changelog.
**Acceptance Criteria:**
- [Happy] `pip install fintracker-<name>` pulls in only the dependencies listed in its `pyproject.toml`.
- [Alt] Installing a service that pins `httpx==0.27.2` with the library resolves without a conflict.
- [Fail] A repository check fails when a dependency has an exact pin, no upper bound, or is an import of a service package.
- [Fail] A repository check fails when a library imports a package that is not declared as a dependency.
**Refs:** LB-IHTTP (dependencies: `httpx`, `botocore`)

---

## 5. Open Questions (consolidated)

| # | Question | Blocks |
|---|---|---|
| 1 | Private package repository (AWS CodeArtifact, proposed) or install from a git tag? CodeArtifact enforces immutable versions and uses IAM in builds, but adds Terraform and a login step in Docker and Lambda builds. A git-tag install needs no new infrastructure, but tags can be moved and builds need a repository token. | LB-PKG-04, LB-PKG-05 |
| 2 | Do the services live in the same repository as `libs/`, or in separate ones? The spec works for both because services install from the repository, but it decides where Renovate runs and whether a library change can also run service tests in the same pull request. | LB-PKG-06 |

---

## Appendix A: Library layout

```
libs/<name>/
  pyproject.toml          # name = "fintracker-<name>", version = "X.Y.Z", requires-python = ">=3.12"
  README.md               # what it is, install, usage, settings table, public API list
  CHANGELOG.md
  src/fintracker_<name>/
    __init__.py           # __version__, __all__
    py.typed
  tests/
libs/scripts/
  version_report.py
  check_libs.py           # layout, pins, dependency and API-diff checks
```

## Appendix B: What each version bump means

| Change | Bump |
|---|---|
| Bug fix, no documented behavior change | Patch |
| New optional parameter, new function, new setting with the old behavior as default | Minor |
| Name deprecated (still works) | Minor |
| New runtime dependency | Minor |
| Removed or renamed public name, changed signature, changed default, tightened validation that rejects previously valid input | Major |
| Dropped a Python version | Major |
| Change inside a name not in `__all__` | Patch |

## Appendix C: Changelog format

```markdown
# Changelog

## Unreleased

## 1.2.0 - 2026-11-12
### Added
- `InternalClient.post` accepts `idempotency_key`.
### Deprecated
- `forwarded_headers()`; use `UserContext.headers()`. Removed in 2.0.0.
### Security
- (none)

## 1.1.1 - 2026-11-03
### Fixed
- Retry delay no longer exceeds the total deadline.
```

## Appendix D: Release and upgrade checklist

**Releasing a library**
1. Move `Unreleased` to a new dated section; choose the bump from Appendix B.
2. Set the version in `pyproject.toml`.
3. Open a pull request; CI runs layout, API-diff, changelog and tests.
4. After merge, push the tag `<distribution name>-v<version>`.
5. Confirm the release job published it and that upgrade pull requests appeared.

**Upgrading a service**
1. Read the changelog items under Changed, Deprecated and Removed.
2. Change the pin; run the service's tests and the conformance suite.
3. Merge; confirm the startup log line shows the new version.

**Pin syntax**

| File | Line |
|---|---|
| `requirements.txt` | `fintracker-internal-http==1.2.0` |
| `pyproject.toml` | `"fintracker-internal-http==1.2.0"` |

---

## Change Log

| Change | Reason |
|---|---|
| New spec | Give shared libraries one packaging, versioning and upgrade process so a library change reaches services in a controlled way |
