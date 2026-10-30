# XS-ACCT-04: purging stored account numbers on deploy

Applies to every environment that holds accounts created before the last-four change. The two
migrations do the database part on their own. The steps below are what a person has to do around them.

## What the migrations do
- `V32__Account_Last_Four.sql` adds `account_last_four`, fills it from `account_number` for every user's
  rows, then drops `account_number`. It runs in one transaction. If any step fails the transaction rolls
  back, Flyway stops and the deploy fails with `account_number` still in place.
- `V33__Rewrite_Accounts_Table.sql` runs `VACUUM FULL ledger.accounts`, so the dropped values are gone
  from the table's pages. Flyway runs it on its own, outside a transaction. The table takes a short
  exclusive lock; it is small.

## Before the deploy
1. The migration user must own `ledger.accounts` (it needs to switch `FORCE ROW LEVEL SECURITY` off and on).
2. Take no new manual Aurora snapshot until the deploy is done.

## After the deploy
1. Check: `SELECT column_name FROM information_schema.columns WHERE table_schema = 'ledger' AND table_name = 'accounts'`
   has no `account_number`, and `ledger.flyway_schema_history` shows V32 and V33 as successful.
2. Check RLS: `SELECT relforcerowsecurity FROM pg_class WHERE oid = 'ledger.accounts'::regclass` is `true`.
3. Delete every manual Aurora snapshot taken before the deploy; they still hold the full numbers.
4. Write in the release notes that automated backups age out on their own (1 day in dev) and that
   point-in-time restore inside that window can still return the old values.

## Rollback
There is none by design: the full numbers are not kept anywhere. Restoring a pre-deploy snapshot would
bring them back, which is why step 3 deletes them.
