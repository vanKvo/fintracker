# Front-End Design Token & Style Guide: Wealth & Growth (Option 1)
**Author & Engineer:** Van Vo
**Project Context:** FinTracker / Verity Portal Modernization
**Effective Dates:** Active (2026)
**Reference Implementation:** `fintracker-ui/src/app/features/accounts/` (Accounts tab) — when in doubt about how a rule below should look in practice, match the Accounts tab.

This document establishes the strict architectural and design tokens for the "Wealth & Growth" layout. It serves as a comprehensive visual instruction set for AI systems, front-end engineers, and UI tools to generate cohesive, WCAG-compliant web components. All new UI elements must comply with these standards.

---

## 1. Core Color Tokens (The 60-30-10 Rule)

To prevent visual fatigue and maximize layout structure, enforce the strict distribution ratio below. The primary backdrop is kept crisp and clear to prioritize clean data visualization.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     60% Dominant (Canvas & Backgrounds)                │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░ #FFFFFF / #FAFAFA ░░░░░░░░░░░░░░░░░░░░░░░░░░ │
├──────────────────────────────────────────┬───────────────────────────┤
│ 30% Structural (Layout & Nav)             │ 10% Accent (Conversion)   │
│ ████████████ #155E37 ████████████████████ │ ▓▓▓▓▓▓▓▓ #D4AF37 ▓▓▓▓▓▓▓ │
└──────────────────────────────────────────┴───────────────────────────┘
```

| Token Name (CSS Custom Property) | Hex Code | Target UI Architecture & Usage |
| :--- | :--- | :--- |
| `--color-bg-primary` | `#FFFFFF` | Global application canvas, main dashboard backdrops, data card faces. |
| `--color-bg-secondary` | `#FAFAFA` | Page-view wrapper background, alternating table rows, subtle sectional wrappers. |
| `--color-brand-primary` | `#155E37` | **Forest Green:** Main sidebar background, primary CTA hover states, brand wordmark. |
| `--color-brand-accent` | `#D4AF37` | **Champagne Gold:** Primary action buttons, active states, brand icon. |
| `--color-text-main` | `#111827` | Primary reading text, body typography, page/section titles, table cell text. |
| `--color-text-muted` | `#4B5563` | Secondary data labels, subtitles, metadata, table header text. |

All six tokens are defined once, globally, in `fintracker-ui/src/styles.scss` under `html { ... }`. **Never hardcode these hex values in a component stylesheet — always reference the CSS custom property.** A prior audit (2026-07) found four pages (Dashboard, Budgets, Reports, Settings) referencing custom properties that were never defined anywhere (`--text-dark`, `--text-secondary`, `--status-success`, `--status-warning`, `--status-error`, `--primary-blue`, `--surface-gray`, `--secondary-light-blue`) — these silently fell back to inherited/default browser styling. Before using `var(--some-token)`, confirm it's one of the tokens actually defined in `styles.scss`.

---

## 2. Functional Status Palette (Sleek Muted System)

Do not use high-saturation or "neon" colors for system states. Status badges and notifications must leverage low-opacity backgrounds with highly saturated, contrasting text elements to look elegant and premium.

| State | Background Token | Text Token | UI Element Mapping |
| :--- | :--- | :--- | :--- |
| **Success** | `--color-success-bg` (`#E2ECE9`) | `--color-success-text` (`#0E3A2F`) | Posted transactions, verified account links, income amounts. |
| **Warning** | `--color-warning-bg` (`#FBF2E2`) | `--color-warning-text` (`#8A5E13`) | Pending approvals, pending-row highlighting, approaching budget limits. |
| **Error** | `--color-error-bg` (`#FCECEB`) | `--color-error-text` (`#8C2520`) | Deleted/failed records, expense amounts, validation failures. |
| **Info** | `--color-info-bg` (`#EDF2F7`) | `--color-info-text` (`#2B4356`) | Analytical tips, platform notifications, transactional metadata hints. |

---

## 3. Typography & Font Layout Tokens (Sleek Swiss Tech)

This typography scheme pairs geometric precision for operational interface layouts with technical monospace uniformity for high-density financial data reporting.

### Font Family Stacks
* **UI Elements & Headers** — `--font-primary`: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`.
* **Financial Data & Tabular Columns** — `--font-mono`: `'JetBrains Mono', 'SF Mono', Menlo, Monaco, Consolas, monospace`.

Both are forced globally in `styles.scss` (the primary font on nearly all Material/HTML text elements via `!important`; the mono font on any element carrying `.financial-value`, `.mono-text`, `.summary-val`, `.financial-data-table`, `.account-number`, or `.balance-text`). Any element rendering a dollar amount, percentage, or account number should either carry one of those classes or explicitly set `font-family: var(--font-mono)`.

### Page Title Format Standard

Every tab's primary page heading (`.page-title`, `.view-title`, or equivalent — one `<h1>`/`<h2>` per page) must use exactly this spec. This is the Accounts tab's `.card-title`, adopted app-wide:

```css
.page-title /* or .card-title, .view-title */ {
  font-family: var(--font-primary);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-main);
  margin: 0;
}
```

Section-level sub-headings inside a page (e.g. Statements' `.section-title`, `.detail-title`) are a distinct visual tier and may use `--color-brand-primary` to differentiate from the page title — that's intentional hierarchy, not inconsistency.

### Table Format Standard

Every `mat-table` must use exactly this header/cell spec. This is the Accounts tab's `.accounts-table`, adopted app-wide:

```css
th.mat-mdc-header-cell {
  background-color: #f8fafc;
  color: var(--color-text-muted);
  font-weight: 700;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  font-family: var(--font-primary);
}

td.mat-mdc-cell {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
  color: var(--color-text-main);
  font-size: 13.5px;
  font-family: var(--font-primary);
}
```

Dollar-amount and account-number columns additionally get `font-family: var(--font-mono); font-variant-numeric: tabular-nums;`.

---

## 4. UI Component Application Architecture

When generating component code (HTML, CSS, Tailwind, or component libraries), adhere to these explicit mapping blueprints:

### A. Main Dashboard Shell
- **Sidebar Navigation:** Background must be `--color-brand-primary`. Active menu selection items use text or marker decoration in `--color-brand-accent`.
- **Main Workspace Canvas:** Background must use `--color-bg-primary`. The page-view wrapper (outside individual cards) uses `--color-bg-secondary`. Section groupings are layered over card surfaces with a 1px `#e2e8f0` border and `border-radius: 8px`.

### B. High-Conversion Buttons (Primary Call-to-Actions)
- **Background:** `--color-brand-accent` (gold).
- **Text Color:** `#FFFFFF` (white). **Never `--color-brand-primary` (green) text on a gold background** — see the color-combination rule below.
- **Interactive Hover State:** Shift background to `--color-brand-primary` (green) and text stays `#FFFFFF` (white).

### C. Financial Metric Displays (Balances, Charts, Logs)
- All financial metrics, dollar values, percentages, and database timestamps must render in `--font-mono`.
- Positive growth markers or trends use `--color-success-text`; negative drops use `--color-error-text`.

### D. Color Combination Rule — Never Mix Yellow/Gold with Green

**A single UI element's background and foreground (or two colors paired directly together — e.g. a badge, button, or chip) must never combine a yellow/gold tone with a green tone.** Pick one of:
- **Gold background → white text/icon** (or white background → gold text/icon), or
- **Green background → white text/icon** (or white background → green text/icon).

This was found violated in seven places during the 2026-07 audit — every primary CTA button (`Login`, `Register`, `Landing` primary CTA, `Add Account`, `Link New Account`, `Upload Statement` hover, `Statement CTA` hover) was rendering green text directly on a gold background, and the `Landing` plan badge did the same. All were corrected to white text on gold.

This rule governs interactive components (buttons, badges, chips, alerts) — it does not apply to the static brand logo lockup (gold icon + green wordmark sitting side by side in the navbar/login/register headers), which is the fixed brand identity mark, not a background/foreground color pairing.

---

## 5. Architectural Compliance Prompt Checklist for AI Generation

When executing code synthesis tasks based on this configuration, verify the following parameters:

- [ ] Is pure `#000000` entirely omitted for text layers? (Use `--color-text-main`, `#111827`.)
- [ ] Are all tabular integers aligned perfectly using a monospaced structure? (Use `--font-mono`.)
- [ ] Does the accent color (gold) constitute less than or equal to roughly 10% of the overall layout area?
- [ ] Do background notification alerts use the soft functional tints (Section 2) instead of primary branding greens?
- [ ] Does every `var(--token)` reference an actual custom property defined in `styles.scss`? (No `--text-dark`, `--primary-blue`, etc.)
- [ ] Does the page title match the Page Title Format Standard (Section 3) exactly?
- [ ] Does every `mat-table` match the Table Format Standard (Section 3) exactly?
- [ ] Does no single UI element pair yellow/gold with green (Section 4.D)?
