# QuantDesk

A personal quant options analysis terminal for one retail trader. It screens,
structures, sizes, backtests, and journals option-selling trades. **It never
executes anything** — you place every trade manually in your brokerage.

## The edge hypothesis (why this exists)

The volatility risk premium (VRP): S&P 500 implied volatility has historically
exceeded subsequently realized volatility (~19.3% implied vs ~15.1% realized,
1990–2018), and options-selling benchmarks (Cboe PUT, BXM, BXMD) have shown
superior risk-adjusted returns versus buy-and-hold. QuantDesk systematically
sells that overpriced insurance — cash-secured puts, covered calls, the wheel —
with strict rules on sizing, correlation, and event risk. It does **not**
predict direction. Every module traces back to measuring, harvesting, or
risk-managing the VRP.

## 10-minute quickstart

```bash
cd quantdesk
pip install -e ".[dev]"

# First run creates config.yaml with defaults — edit it before trusting output:
quantdesk config-show

# Volatility snapshot for any symbol (also records today's ATM IV
# observation, building your own IV-rank history over time):
quantdesk quote AAPL

# Where are we in the vol cycle, and what's the sizing multiplier?
quantdesk regime

# Browser dashboard (read-only; needs `pip install -e ".[dashboard]"`):
quantdesk dashboard
```

Then open `config.yaml` and check:

1. `account.size` — deployable capital in CAD (starts at the confirmed $100;
   update it as the account grows — sizing caps scale off this number).
2. `account.account_type` — `tfsa` or `margin`. TFSA hides credit spreads
   (registered-account strategy limits, plus CRA business-income caution for
   high-frequency option writing).
3. `costs.per_contract_fee` — US$0.75/contract (Wealthsimple Core tier;
   still to be double-checked against their fee page — Premium/Generation
   advertise reduced options fees).
4. `watchlist` — add/remove names. Ships with ~75 liquid names: US large
   caps, major ETFs, and Canadian companies via their US cross-listings.

## Canadian trader specifics

- **Wealthsimple supports US-listed options only**, and yfinance carries no
  Montreal Exchange chains. TSX exposure therefore comes through the US
  cross-listings of Canadian names (SHOP, RY, TD, BMO, BNS, ENB, CNQ, SU,
  CP, CNI, AEM, CCJ, BN, …), which the default watchlist includes. Pure
  TSX-only tickers (`.TO`) can still be quoted for spot/realized-vol, but
  have no tradeable chains here.
- **Currency:** account size is tracked in CAD; option collateral and
  premiums are USD. Phase 4 sizing converts with a live CADUSD quote from
  the provider rather than a hardcoded rate.
- **Small-account honesty:** at $100 CAD (~$73 USD) no cash-secured put is
  affordable — the cheapest realistic CSP collateral is several hundred
  dollars. The screener will correctly return *zero* affordable candidates
  rather than pretending. Until the account grows, the productive daily
  habit is running `quantdesk quote` on the watchlist to build IV history,
  and (once Phase 5 lands) paper-journaling proposals to validate the
  process.

## The weekly operating loop

| When | What | Command |
|------|------|---------|
| Sunday | Scan the universe for rich premium | `quantdesk scan --strategy csp` |
| Sunday | Structure the best candidates | `quantdesk propose csp XYZ` |
| Sunday | Size them; the risk engine blocks rule violations | *(Phase 4)* |
| Monday | **You** execute manually at the broker | — |
| Same day | Journal the fill | `quantdesk journal open SHOP --strike 95 --expiry ... --credit 0.90` |
| Daily | Check exits: 50% profit / 21 DTE / 2× credit stop | on every proposal card |
| At exit | Close/assign in the journal (P&L computed for you) | `quantdesk journal close 1 --cost 30 --reason take-profit` |
| Monthly | Review: rule adherence, IV-sold vs realized, autopsy | `quantdesk review --month 2026-07` |
| Anytime | Validate the strategy on history (synthetic pricing) | `quantdesk backtest wheel SPY --years 6` |

## Build status

- [x] **Phase 1 — Data layer + options math core**: yfinance provider with
  SQLite TTL cache, Black-Scholes pricing/Greeks/IV solver (Brent), realized
  vol suite (close-to-close, Parkinson, Yang-Zhang), IV rank with home-grown
  IV history, VRP estimate, expected move, POP/prob-of-touch, VIX regime
  classifier, `quote`/`regime`/`config-show` CLI.
- [x] **Phase 2 — Screener**: watchlist universe, composable filter
  pipeline (liquidity, vol richness, earnings blackout, affordability
  with live-FX CAD→USD caps, freefall exclusion), composite z-scored
  opportunity ranking, `scan --strategy csp` with fully queryable
  exclusions via `scan --explain SYMBOL`.
- [x] **Phase 3 — Strategy engine**: TradeProposal cards with legs,
  credit, max profit/loss, collateral, breakevens, dual POP estimates
  (delta approx + lognormal), entry Greeks in trader units, plain-English
  thesis, and a mechanical exit plan (50% take-profit / 21 DTE / 2x-credit
  stop) on every card. CSP, covered call (cost-basis aware), put credit
  spreads (margin-gated, min credit >= 1/3 width), and the wheel state
  machine with exact effective-cost-basis accounting.
- [x] **Phase 4 — Risk engine**: fractional-Kelly sizing estimated from
  POP + the exit-plan payoff, always bounded by fixed-fraction hard caps
  and the VIX-regime multiplier (halve >30, freeze >40); portfolio
  aggregation (dollar Greeks, beta-weighted delta to SPY, sector counts,
  pairwise 90d correlations); hard rule engine (position cap, deployment
  cap, sector concentration, correlation warning, VIX freeze) with
  BLOCK/WARN severities. `propose` now ends with a sizing panel.
- [x] **Phase 5 — Backtester + journal**: event-driven daily loop for
  CSP/wheel/covered-call with synthetic BS pricing (RV20 x richness IV
  proxy — every report screams the limitation), punitive cost model
  (per-contract fees + moneyness/DTE-scaled spread slippage), full
  metrics panel (CAGR, Sharpe, Sortino, max DD + duration, ulcer,
  CVaR95, win rate, premium capture) vs buy-and-hold and SPY, plotly
  HTML reports to `reports/`, walk-forward validation with an overfit
  flag; SQLite journal (open/adjust/close/assign, computed P&L,
  permanent override records) and the monthly review (rule adherence,
  IV-sold vs realized "closing-line value", worst-trade autopsy).
- [x] **Phase 6 — Streamlit dashboard**: `quantdesk dashboard` serves a
  read-only browser UI over the same SQLite DB — Scanner (ranked table +
  click-through proposals), Portfolio (open positions, deployment gauge,
  90d correlation heatmap), Journal (cumulative P&L curve, trade table,
  monthly review), Regime (VIX level/term structure, sizing multiplier,
  1y chart). Each tab has its own error boundary, so being offline
  degrades a tab instead of killing the page; the Journal tab is fully
  offline. The CLI remains the workhorse.

## Development

```bash
pytest            # every analytics formula has a known-value test
mypy              # --strict, configured in pyproject.toml
```

## LIMITATIONS — read this before trusting any number

- **yfinance data quality.** Free data: quotes are delayed, option chains have
  stale/NaN bids and asks, the earnings calendar is unreliable, and its IV
  field is junk (QuantDesk re-solves IV from mid prices with its own solver).
  A `DataProvider` abstraction exists so a paid feed (Polygon, Tradier, FMP)
  can be swapped in without touching strategy code.
- **No IV history exists for free.** IV rank needs a year of IV observations;
  QuantDesk builds its own by recording ATM IV each time you run `quote`.
  Until ~252 daily observations exist the rank is labeled IMMATURE — treat it
  as noise early on.
- **Synthetic backtests (Phase 5) are approximations.** Historical option
  prices aren't free, so backtests price options from realized-vol proxies.
  Directional/regime validity only; absolute return figures are approximate.
- **No intraday anything.** Daily bars, daily decisions. This is a
  weekly-cadence system, not a day-trading tool.
- **Estimates everywhere.** POP, expected move, and probability of touch are
  lognormal-model outputs. Real markets have fat left tails.
- **The VRP is not free money.** It is compensation for carrying tail risk —
  the seller's occasional large loss is the product being sold. Sizing caps
  and the VIX-regime circuit breaker exist because the premium's worst
  drawdowns arrive exactly when everything else is falling.
- **The European pricing model** (Black-Scholes-Merton) approximates American
  equity options. Good for short-dated OTM contracts; weakest for deep-ITM
  and imminent-dividend situations (the assignment-risk heuristic flags these).
- **Taxes are on you.** TFSA/CRA notes in the tool are reminders, not advice.
