# Bug name: Account number was masked server-side, so inline-edit could never recover the full value

## Problem
REQ-3.1.D says: "Account number: Alphanumeric letters only. For the Accounts table in the UI, we can show the last four digits, while record the full account number in the database." The database side was correct — `ledger.accounts.account_number` stored the full value — but `JooqAccountRepository` masked it down to the last 4 digits before it ever left the backend. `AccountDto` only ever exposed `accountNumberLast4`, never the full number.

This meant `fintracker-ui`'s Accounts table couldn't fully implement inline editing for account number: `startEdit()` had nothing but the masked value (`"6789"`) to prefill the edit input with, so a user opening inline edit on an account saw only 4 digits in the "Account Number" field instead of the real number — editing it meant blindly retyping the whole thing rather than correcting a value they could actually see.

### Root cause:
Masking was implemented at the wrong layer — in the repository (server-side, on read) instead of the UI (client-side, on display). `AccountDto.accountNumberLast4` and `JooqAccountRepository.mapToAccountDto()`'s `maskLast4()` call meant the full account number was write-only: accepted by `CreateAccountRequest`/`UpdateAccountRequest` and persisted, but never read back out through any API response.

### Code with bug:
```java
// AccountDto.java
public record AccountDto(
        UUID accountId,
        UUID userId,
        String accountName,
        String accountType,
        String accountNumberLast4,
        String owner,
        BigDecimal currentBalance,
        String syncMode,
        OffsetDateTime createdAt
) {}
```
```java
// JooqAccountRepository.java
private AccountDto mapToAccountDto(Record record) {
    return new AccountDto(
            record.get("account_id", UUID.class),
            record.get("user_id", UUID.class),
            record.get("account_name", String.class),
            record.get("account_type", String.class),
            maskLast4(record.get("account_number", String.class)),
            record.get("owner", String.class),
            record.get("current_balance", BigDecimal.class),
            record.get("sync_mode", String.class),
            record.get("created_at", OffsetDateTime.class)
    );
}

private static String maskLast4(String accountNumber) {
    if (accountNumber == null) {
        return null;
    }
    return accountNumber.length() <= 4
            ? accountNumber
            : accountNumber.substring(accountNumber.length() - 4);
}
```
```typescript
// accounts.ts
startEdit(row: Account) {
  this.editingAccountId.set(row.accountId);
  this.editAccountNumber = row.accountNumberLast4 || ''; // only ever 4 digits
  ...
}
```

## Solution
Move masking to where REQ-3.1.D actually puts it: the UI display layer. The API now returns the full account number (`AccountDto.accountNumber`), so the Angular `Account` model and the inline-edit form have the real value to work with. The Accounts table masks it to the last 4 digits only at render time, in a small component method — the underlying signal/model still holds the full number.

1. **`AccountDto`**: renamed `accountNumberLast4` → `accountNumber`, documented as the full persisted value.
2. **`JooqAccountRepository`**: removed `maskLast4()`; `mapToAccountDto()` now passes `account_number` straight through.
3. **`AccountServiceTest`**: updated the create-account test to assert the full number passes through unmasked (previously asserted the masked value).
4. **`account.service.ts`** (Angular): `Account.accountNumberLast4` → `accountNumber`.
5. **`accounts.ts`**: `startEdit()` now prefills the edit input with the full `row.accountNumber`; `saveEdit()`'s "did the user actually change it" comparison is now against the full value instead of the masked one; added `maskAccountNumber()` for display.
6. **`accounts.html`**: the read-only table cell renders `maskAccountNumber(element.accountNumber)`; the edit-mode input binds to the full value via `editAccountNumber`, unchanged.

### Fixed Code
```java
// AccountDto.java
public record AccountDto(
        UUID accountId,
        UUID userId,
        String accountName,
        String accountType,
        String accountNumber,
        String owner,
        BigDecimal currentBalance,
        String syncMode,
        OffsetDateTime createdAt
) {}
```
```java
// JooqAccountRepository.java
private AccountDto mapToAccountDto(Record record) {
    return new AccountDto(
            record.get("account_id", UUID.class),
            record.get("user_id", UUID.class),
            record.get("account_name", String.class),
            record.get("account_type", String.class),
            record.get("account_number", String.class),
            record.get("owner", String.class),
            record.get("current_balance", BigDecimal.class),
            record.get("sync_mode", String.class),
            record.get("created_at", OffsetDateTime.class)
    );
}
```
```typescript
// accounts.ts
startEdit(row: Account) {
  this.editingAccountId.set(row.accountId);
  this.editAccountNumber = row.accountNumber || ''; // full value, editable
  ...
}

maskAccountNumber(accountNumber?: string): string {
  if (!accountNumber) {
    return '';
  }
  return accountNumber.length <= 4 ? accountNumber : accountNumber.slice(-4);
}
```
```html
<!-- accounts.html -->
<span class="account-number">{{ maskAccountNumber(element.accountNumber) }}</span>
```
