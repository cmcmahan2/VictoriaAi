# PocketPlan — personal finance (iPhone-first)

A mobile-first budget, debt-payoff and savings tracker. No login and no bank connection: data is stored only in the browser (localStorage), with JSON backup/restore. All amounts are in CAD.

## Run

```
cd finance
npm install
npm run dev        # http://localhost:3002
npm run build      # static site in ./out — deploy to Vercel / Netlify / GitHub Pages
```

On iPhone: open the deployed URL in Safari → Share → **Add to Home Screen**. Safari may clear data for sites you don't use for a while, so export a JSON backup regularly (Settings → Data & backup).

## Screens
- **Home**: next payday and paycheque logging, the paycheque split checklist, the current phase, debt-free date, net worth, emergency fund and Wealthsimple totals, money left this week, spending pie, and a planned vs actual % of income ring
- **＋ Check-in**: nightly "What did you spend today?". Type `35 bowling + drinks` and the category is guessed (one tap to change). Add several items, or tap "Nothing today". Includes a streak counter.
- **Spending**: weekly/monthly views, category bars (yellow at 80%, red over budget), search, edit/delete
- **Debt**: the 3-phase plan, a payoff timeline chart, and per-debt progress, payments, projected payoff and deadline check
- **More → Savings**: emergency fund progress, the FHSA/TFSA contribution log and limits, a manual current value, and a checklist
- **More → Work vehicle**: trips (one-tap Abbotsford repeat), fill-ups, a weekly summary, YTD business-use %, CSV export and a printable logbook
- **More → Import**: RBC / Tangerine / Amex CSV, auto-categorize rules, duplicate matching against your manual logs, and "thought vs actual"
- **More → Settings**: every budget, plan amount, debt and limit; backup/restore; copy monthly summary

## Code map
- `lib/calc.ts`: budgets, phases, paycheque split, payoff projection (simulated payday by payday), streak
- `lib/csv.ts`: CSV parsing, column/sign auto-detection, categorizing, duplicate detection
- `lib/summary.ts`: plain-text monthly summary for pasting into Claude
- `lib/defaults.ts`: all default numbers (edit in-app via Settings)
