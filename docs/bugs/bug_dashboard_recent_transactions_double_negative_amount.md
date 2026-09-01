# Bug name: Recent Transactions rendered expense amounts with a doubled minus sign

## Problem

In the Dashboard's Recent Transactions table, every expense row rendered its amount with two
negative signs — `- -$45.00` instead of `-$45.00`. Income rows were unaffected.

A second, related defect in the same table: the sign was chosen by comparing the row's **category**
against the literal string `'Income'`, so any credit that was not categorised exactly as `Income`
(a refund, a transfer in, a reimbursement) rendered with a leading minus despite being money
received.

### Root cause

Expenses are stored as negative amounts. The template prefixed a hand-written sign character and
then passed the raw amount to the `currency` pipe, which renders its own sign for negative values —
so the two compounded.

The sign was also derived from the wrong field. Category is a classification label; the direction of
money movement is carried by the sign of `amount`. Using the former to describe the latter only
holds while every credit happens to be categorised `Income`.

### Code with bug

```html
<!-- dashboard.html -->
<ng-container matColumnDef="amount">
  <th mat-header-cell *matHeaderCellDef> Amount </th>
  <td mat-cell *matCellDef="let element"
      [ngClass]="{'expense-amount': element.category !== 'Income', 'income-amount': element.category === 'Income'}">
    {{element.category === 'Income' ? '+' : '-'}} {{element.amount | currency}}
  </td>
</ng-container>
```

For an expense of `-45`, this emits `-` followed by `currency(-45)` → `- -$45.00`.

## Solution

Drop the hand-written sign and let the `currency` pipe render it, and key the colour classes off the
sign of `amount` rather than off the category label.

1. Remove the `{{element.category === 'Income' ? '+' : '-'}}` prefix.
2. Switch the `ngClass` condition from `element.category !== 'Income'` to `element.amount < 0`.
3. Add a comment recording why no sign is prefixed, so it is not "helpfully" restored later.

While in the same table, two presentation fixes were applied alongside: the raw ISO date is now run
through the `date` pipe (`MMM d, y`) instead of rendering as `2026-08-06`, and the amount column
uses the mono font stack with `tabular-nums` per the Table Format Standard in
`docs/color_schema/color_schema.md`, so the decimal points align down the column.

### Fixed Code

```html
<!-- dashboard.html -->
<ng-container matColumnDef="amount">
  <th mat-header-cell *matHeaderCellDef class="amount-header"> Amount </th>
  <td mat-cell *matCellDef="let element" class="amount-cell"
      [ngClass]="{'expense-amount': element.amount < 0, 'income-amount': element.amount >= 0}">
    <!-- The currency pipe already renders the sign; prefixing one produced "- -$45.00". -->
    {{element.amount | currency}}
  </td>
</ng-container>
```

```scss
// dashboard.scss — Table Format Standard, Section 3
.amount-header { text-align: right; }

.amount-cell {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
}
```
