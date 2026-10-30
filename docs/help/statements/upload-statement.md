# Statements

<!-- verify: accepted file types and size limit; exact labels in the upload form; whether opening/closing dates are asked for every format; names of statuses in the table. -->

## Upload a statement

Statements are how your transactions get into FinTracker. You upload a bank statement file, FinTracker reads it, and the transactions appear as pending rows for you to approve.

To upload, open the Statements tab and start a new upload:

1. Choose the account the statement belongs to.
2. For a CSV file, choose the bank. Banks lay out their exports differently, so FinTracker needs to know which one.
3. Check the statement's start and end dates. For a CSV, they are filled in from the file's dates, and you can correct them.
4. Choose or drop the file.
5. Submit.

You can upload a CSV, a PDF or a photo of a statement.

## One statement per account per month

An account can have only one statement for each calendar month. The month is taken from the statement's end date. If you try to upload a second statement for the same account and month, FinTracker tells you and asks what to do. See "Duplicate statements".

## Duplicate statements

FinTracker warns you when a statement looks like one you already uploaded. It checks for the exact same file, for a statement covering the same month on the same account, and for a re-exported file whose transactions match an earlier upload.

A dialog shows the existing statement with its upload date and transaction count, and you choose:

- **Overwrite:** deletes the older statement and all its transactions, then imports the new file. This cannot be undone.
- **Cancel:** stops the upload and keeps what you have.

## Processing and status

After you submit, the statement appears in the list as Processing. The page checks progress every few seconds, so you do not need to refresh.

- **Processing:** FinTracker is reading the file.
- **Completed:** every transaction was imported.
- **Partially completed:** some rows could not be read. The rows that were read are imported.
- **Failed:** the import did not finish. You can try again.

For a CSV, processing pauses so you can confirm which column is which. See "CSV mapping".

## After the import

Imported transactions arrive as pending. Open the Transactions tab to review and approve them. Budgets, the Dashboard and Reports include a transaction only after you approve it.

## If the upload fails

If you see "Upload failed. Please try again.", try the upload again. If it fails again, check that the file is a CSV, PDF or image, and that you chose the right account and bank.

A statement can also fail if FinTracker finds after upload that it duplicates an existing statement. Delete the older one or choose a different file.

A paused import that you do not finish within about 30 minutes expires. Start the upload again.
