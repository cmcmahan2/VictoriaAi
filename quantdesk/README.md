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
```

Then open `config.yaml` and set:

1. `account.size` — your real deployable capital (default 10,000 is a placeholder).
2. `account.account_type` — `tfsa` or `margin`. TFSA hides credit spreads
   (registered-account strategy limits, plus CRA business-income caution for
   high-frequency option writing).
3. `costs.per_contract_fee` — confirm Wealthsimple's current options fee
   schedule; the US$0.75/contract default is a placeholder.
4. `watchlist` — add/remove names. Ships with ~60 liquid large caps and ETFs.

## The weekly operating loop

| When | What | Command |
|------|------|---------|
| Sunday | Scan the universe for rich premium | `quantdesk scan --strategy csp` *(Phase 2)* |
| Sunday | Structure the best candidates | `quantdesk propose csp XYZ` *(Phase 3)* |
| Sunday | Size them; the risk engine blocks rule violations | *(Phase 4)* |
| Monday | **You** execute manually at the broker | — |
| Same day | Journal the fill | `quantdesk journal open ...` *(Phase 5)* |
| Daily | Check exits: 50% profit / 21 DTE / 2× credit stop | on every proposal card |
| Monthly | Review: rule adherence, IV-sold vs realized, autopsy | `quantdesk review` *(Phase 5)* |

## Build status

- [x] **Phase 1 — Data layer + options math core**: yfinance provider with
  SQLite TTL cache, Black-Scholes pricing/Greeks/IV solver (Brent), realized
  vol suite (close-to-close, Parkinson, Yang-Zhang), IV rank with home-grown
  IV history, VRP estimate, expected move, POP/prob-of-touch, VIX regime
  classifier, `quote`/`regime`/`config-show` CLI.
- [ ] Phase 2 — Screener (universe, filter pipeline, composite score)
- [ ] Phase 3 — Strategy engine (CSP, covered call, credit spreads, wheel)
- [ ] Phase 4 — Risk engine (Kelly sizing, portfolio Greeks, hard rules)
- [ ] Phase 5 — Backtester + journal
- [ ] Phase 6 — Streamlit dashboard

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
