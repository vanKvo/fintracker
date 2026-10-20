# Ledger Statement(Spec 03)

## REQ-STMT-09: Automatically filling opening/closing dates before sending the API request for uploading a statement.

### Problem

Currently, the user has to manually type the opening and closing dates when uploading a CSV statement, leading to potential typos or bad date ranges.

### Requested Changes (On frontend side related to uploading statement)
The server expects openingDate and closingDate sent upfront during initiateUpload. This approach simply populates those parameters automatically on the frontend before sending the API request.

Step-by-Step Approach:

1. Detect & Parse File: On file selection, if the file is a CSV (isCsv()), read it as text using FileReader (or PapaParse) directly in the browser.

2. Find the Date Column: Use a simple heuristic:
- Look for a header named "date" (matching the server's backend logic in gatekeeper/service.py).
- Fallback: If headers are missing or ambiguous, pick the column containing the highest density of parseable date values.

3. Pre-fill Range Signals: Parse all dates in that column, find the minimum (earliest) and maximum (latest) values, and auto-populate the openingDate and closingDate UI fields.

4. Keep Controls Editable: Leave the inputs editable so users can correct edge cases (e.g., unusual date formats or reversed column order). Existing validation (dateRangeInvalid) will still catch bad date inputs if the user or parser gets it wrong.