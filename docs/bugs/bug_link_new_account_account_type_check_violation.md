# Bug name: "Link New Account" always fails — accountType values don't match the DB CHECK constraint

## Problem
Creating a new account via the "Link New Account" dialog on the Accounts page always failed, showing the generic "Failed to link account. Please verify details." error toast regardless of what the user entered.

### Root cause:
`ledger.accounts.account_type` has a hard `CHECK` constraint (`V1__Initial_Schema.sql`, confirmed live on the running database as `accounts_account_type_check`) allowing exactly three uppercase values:
```sql
account_type VARCHAR(50) NOT NULL CHECK (account_type IN ('CHECKING', 'SAVINGS', 'CREDIT'))
```
The "Link New Account" dialog's dropdown (`add-account-dialog.ts`) offered a completely different, mismatched set of values: `'Checking'`, `'Savings'`, `'Credit Card'`, `'Investment'` — mixed case, and two of the four (`'Credit Card'`, `'Investment'`) don't correspond to any allowed value at all.

`AccountServiceImpl`'s application-level validation only checks character class (`NAME_FIELD_PATTERN` — letters/digits/space/hyphen), not enum membership, so every one of these values passes backend validation and reaches the `INSERT`. Postgres then rejects it with a `CHECK` constraint violation — a `DataIntegrityViolationException` with no explicit handler, surfacing as a 500 and the frontend's generic error message. Since none of the four dropdown options ever matched the constraint, account creation had a 100% failure rate regardless of what the user picked.

The same class of bug existed in the Accounts table's inline-edit row for `accountType`, which was a free-text `<input>` with no constraint at all — editing an account's type to anything but exactly `CHECKING`/`SAVINGS`/`CREDIT` would hit the same `CHECK` violation on `PATCH`.

### Code with bug:
```typescript
// add-account-dialog.ts
accountType = signal('Checking');
accountTypes = ['Checking', 'Savings', 'Credit Card', 'Investment'];
```
```html
<!-- accounts.html — inline edit, no constraint at all -->
<input type="text" class="table-input" [(ngModel)]="editAccountType" />
```

## Solution
Conform the frontend's account-type selection to what the database actually accepts, rather than expanding the database constraint — `'Credit Card'` and `'Investment'` aren't currently modeled at all in `ledger.accounts`.

1. **`add-account-dialog.ts`**: `accountTypes` is now `[{value:'CHECKING',label:'Checking'}, {value:'SAVINGS',label:'Savings'}, {value:'CREDIT',label:'Credit'}]` — the dropdown displays a friendly label but only ever emits one of the three DB-valid values (same value/label-pair pattern already used for `syncMode`'s options elsewhere in the app). Default changed from `'Checking'` to `'CHECKING'`.
2. **`accounts.ts`**: added the same `accountTypes = ['CHECKING', 'SAVINGS', 'CREDIT']` list; removed the now-unreachable character-class check on `accountType` in `saveEdit()` (a constrained `<select>` can't emit an invalid value, same as `syncMode` has no such check).
3. **`accounts.html`**: the inline-edit `accountType` cell is now a `<select>` with the three fixed options, matching the existing `syncMode` `<select>` pattern, instead of an unconstrained text input.

Also checked (per the request to review all constraints on the table): `sync_mode`'s CHECK constraint already matches the UI exactly (`MANUAL`/`AUTOMATED`); `account_name`/`account_type`/`account_number`/`owner` VARCHAR length limits (100/50/50/255) aren't currently hit by any UI input; the table's forced Row-Level Security policy (`accounts_isolation`, `user_id = current_setting('app.current_user_id')`) applies symmetrically to all commands and isn't implicated, since reads already worked.

### Fixed Code
```typescript
// add-account-dialog.ts
accountType = signal('CHECKING');
accountTypes = [
  { value: 'CHECKING', label: 'Checking' },
  { value: 'SAVINGS', label: 'Savings' },
  { value: 'CREDIT', label: 'Credit' }
];
```
```html
<!-- add-account-dialog.html -->
<mat-select [value]="accountType()" (selectionChange)="accountType.set($event.value)">
  @for (t of accountTypes; track t.value) {
    <mat-option [value]="t.value">{{ t.label }}</mat-option>
  }
</mat-select>
```
```html
<!-- accounts.html — inline edit, now constrained -->
<select class="table-select" [(ngModel)]="editAccountType">
  @for (t of accountTypes; track t) {
    <option [value]="t">{{ t }}</option>
  }
</select>
```
