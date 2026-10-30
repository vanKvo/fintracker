# Statements

<!-- verify: dialog title and button labels ("Confirm", field names Date/Merchant/Amount); wording shown to the user when headers are duplicated. -->

## CSV mapping

Every CSV import pauses and asks you to confirm which column holds the date, which holds the merchant and which holds the amount. Banks name their columns differently, so this check makes sure transactions are read correctly. You see this dialog on every CSV upload.

### Confirm columns

When the mapping dialog opens:

1. Look at the proposed column for Date, Merchant and Amount.
2. If a proposal is wrong, choose the correct column from the dropdown.
3. Choose Confirm.

The import then continues. If you confirm without changing anything, the proposal was right and nothing else is needed.

### How the proposal is chosen

FinTracker proposes columns in this order, using the first one it finds:

1. The mapping you confirmed earlier for the same bank and file layout.
2. The standard mapping for that bank and layout.
3. The closest standard mapping for that bank.
4. Default names: date, merchant and amount.

When your own mapping differs from the standard one, the dialog can show a note such as "Most users map Posting Date to Date".

### Your correction is remembered

When you confirm a mapping, FinTracker saves it as yours for that bank and file layout. Your next upload of the same kind is proposed with your columns. Your correction changes only your own proposals and never another person's.

### When your bank changes its CSV format

If the bank adds, removes or renames a column, FinTracker treats it as a new layout and asks you to confirm again. This is normal. Check the proposed columns and confirm.

### Common problems

- **The wrong column is proposed:** pick the right one and confirm. It is remembered for next time.
- **The CSV is rejected for duplicate column names:** open the file and give each column heading a unique name, then upload again.
- **The dialog was left open too long:** a paused import expires after about 30 minutes. Upload the file again.
- **Amounts look wrong after import:** check that the Amount column was the one confirmed, not a balance column. Delete the statement and upload again with the correct column.
