=========================
F2P TESTS (38)
=========================

--- TestLayoutCheck (8) ---
1. a library with every required file passes check_libs: LB-PKG-01 happy path.
2. pip install of a library folder in a clean environment succeeds and the import works: LB-PKG-01 install.
3. __version__ equals the version in pyproject.toml: LB-PKG-01 single source.
4. a library missing README, CHANGELOG, py.typed or tests fails the check: LB-PKG-01 required files.
5. a library with no __all__ fails the check: LB-PKG-01 public API.
6. a version set in a second place fails the check: LB-PKG-01 one version.
7. a type error in the public API fails the type-check step: LB-PKG-01 typing.
8. the library's tests run on Python 3.12 and 3.13: LB-PKG-01 supported versions.

--- TestApiDiff (6) ---
9. a new optional parameter passes with a minor bump: LB-PKG-02 minor.
10. a changed default of a documented setting without a major bump fails: LB-PKG-02 major.
11. removing or renaming a name in __all__ without a major bump fails: LB-PKG-02 breaking.
12. changing a public signature without a major bump fails: LB-PKG-02 breaking.
13. a change inside a name not in __all__ passes as a patch: LB-PKG-02 internal.
14. a version that is not MAJOR.MINOR.PATCH is rejected: LB-PKG-02 format.

--- TestChangelog (6) ---
15. a release section lists every pull request since the last release: LB-PKG-03 happy path.
16. a deprecated name still works and emits one DeprecationWarning naming the replacement: LB-PKG-03 deprecation.
17. a change to src/ without a changelog line fails CI: LB-PKG-03 changelog required.
18. a major release removing a name that was never deprecated fails: LB-PKG-03 announced removal.
19. a changelog without a section for the tagged version fails the release job: LB-PKG-03 release notes.
20. the changelog headings and date format are checked: LB-PKG-03 format.

--- TestRelease (5) ---
21. a tag publishes that version, and pip install of the exact version works from the repository: LB-PKG-04 happy path.
22. a tag for one library builds and publishes only that library: LB-PKG-04 isolation.
23. a tag that does not match pyproject.toml fails and publishes nothing: LB-PKG-04 tag check.
24. a failing test stops publishing: LB-PKG-04 tests gate.
25. publishing an existing version is refused and the existing files are unchanged: LB-PKG-04 immutable.

--- TestPins (5) ---
26. the service build installs exactly the pinned version and logs it: LB-PKG-05 happy path.
27. the service logs its library versions at startup: LB-PKG-05 startup line.
28. two services may pin different versions of one library: LB-PKG-05 independence.
29. a range (>=, ~=, *) for a FinTracker library fails the repository check: LB-PKG-05 exact pins.
30. a build that cannot reach the repository fails and never falls back: LB-PKG-05 no fallback.

--- TestVersionReport (5) ---
31. all services on latest: the table shows versions and exits 0: LB-PKG-07 happy path.
32. one minor behind is shown as "(1 minor behind)" and exits 0: LB-PKG-07 minor lag.
33. a library no service uses appears with no pins: LB-PKG-07 unused.
34. a service a major behind exits non-zero and names the service and library: LB-PKG-07 major lag.
35. a security release not adopted after 14 days exits non-zero: LB-PKG-07 / LB-PKG-08 security due.

--- TestDependencies (3) ---
36. a dependency with an exact pin or no upper bound fails the check: LB-PKG-09 loose pins.
37. an import of a package not declared as a dependency fails the check: LB-PKG-09 declared imports.
38. an import of a service package fails the check: LB-PKG-09 no service imports.

=========================
PROCESS CHECKS (run once when the process is set up, then after changes to it)
=========================

P1. releasing a patch results in an upgrade pull request in each service within 24 hours, merged when CI passes: LB-PKG-06.
P2. releasing a minor waits for review; releasing a major carries the breaking label and the changelog items: LB-PKG-06.
P3. a bump whose CI fails stays open and is not merged: LB-PKG-06.
P4. deleting a published version is refused by the repository policy: LB-PKG-08.
P5. a service pinned to a yanked version makes the report exit non-zero: LB-PKG-08.
P6. a security patch on the previous major within 90 days is released from that major's branch with its own tag: LB-PKG-08.
