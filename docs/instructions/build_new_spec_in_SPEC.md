Don’t edit SPECS.md by hand. Once a spec has the right file name in the right folder, the script adds it.

1. Choose the prefix. Use the service code plus a new feature code, and check in SPECS.md that it isn’t already taken. For example, a Ledger spec for recurring bills could be LG-BILL.

2. Create the file in that service’s specs/ folder, starting from docs/templates/spec_template.md:
Spec: fintracker-ledger-doc/specs/LG-BILL-recurring-bills-spec.md
Title: # LG-BILL: Recurring Bills
Requirement headings: ### LG-BILL-01: <title>, ### LG-BILL-02: …
Tests file, if you have one: LG-BILL-recurring-bills-tests.md, in the same folder

3. Rebuild the index from the repo root:
    python3 docs/scripts/build_spec_index.py
It adds the spec, its tests file and every requirement ID to SPECS.md. Re-run it whenever you add, rename or remove a requirement.

4. Commit the spec and SPECS.md together

To check your work, run python3 docs/scripts/build_spec_index.py --check. It fails, and says why, if you forgot to rebuild or if:
a file name doesn’t follow the pattern;
a prefix is used by two features;
a heading uses another spec’s prefix;
a requirement ID appears twice.