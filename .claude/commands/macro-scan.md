# Macro Scan

A full-spectrum macro market research scan. Pulls live cross-asset data from the
connected Finance (FMP) MCP tools, distills it into signals, and produces ranked,
evidence-backed investment ideas across every time horizon — from this week to a
lifetime.

This is a **research tool for the user's own analysis and personal account.** It is
NOT investment advice, NOT a solicitation, and must never be presented as a
guarantee. See "Guardrails" — they are non-negotiable.

---

## Arguments

`$ARGUMENTS` selects which horizons to run. Empty = run all of them.
Accepted tokens (any combination): `day week month quarter half year multiyear lifetime`.

Examples:
- `/macro-scan` → all horizons
- `/macro-scan day` → the "Right Now" radar only (the daily report)
- `/macro-scan year multiyear` → the 1-year and 2–5-year trade views
- `/macro-scan lifetime` → the long-term allocation framework only

Each horizon renders in one of three **output modes** (defined in Step 3 / Output):
`radar` for `day`, `trade-book` for week→multiyear, `allocation` for `lifetime`.

---

## Guardrails (read first, every run)

1. **No fabricated data.** Every number, level, or trend you cite MUST come from a
   tool call you actually made this run. If a datum isn't available, say "not
   retrieved" — never invent a price, rate, or statistic.
2. **Honesty about edge.** Markets are highly efficient. Most professional managers
   underperform a low-cost index over long horizons. Frame ideas as *probabilistic,
   risk-managed hypotheses*, not predictions. For long horizons, the honest default
   is broad, low-cost, diversified exposure — say so plainly even if it's boring.
3. **Every idea carries its own kill-switch.** No idea is complete without: a
   conviction level, the thesis, the catalyst/timing, the key risks, and the
   explicit condition that would INVALIDATE it.
4. **Not advice.** End every report with the one-line disclaimer (see Output). Do
   not tell the user what they *should* do with their money; present analysis and
   let them decide.
5. **Legal lines.** Only use public data. Never act on or solicit material
   non-public information. This tool is for the user's personal research only.

---

## Step 1 — Collect data (free; no API keys)

Pull broadly but efficiently. **Batch** where you can, and only fetch what the
selected horizons need. Data comes from two complementary free sources:

**(A) Cross-asset levels — run the local fetcher (free, no key):**
```
python macro/datafeed.py
```
This returns current levels + intraday change for equity indices (S&P 500, Nasdaq
100, Dow, Russell via IWM), the **VIX** (via VIX future), commodities (gold, WTI,
copper, nat gas, silver), the **US Dollar Index** + EUR/USD, and crypto (BTC, ETH).
Use it because the FMP `quote` family is blocked on the current plan tier (see
"Known data limits"). Parse its JSON and cite the levels.

**(B) Rates, valuation & internals — FMP MCP tools (the endpoints that work on this tier):**
- **Rates** (`mcp__claude_ai_FMP__economics`): `treasury-rates` (full curve + recent
  history → level, slope/2s10s, direction). ✅ works.
- **Valuation & rotation** (`mcp__claude_ai_FMP__marketPerformance`):
  `sector-PE-snapshot`, `sector-performance-snapshot`, `historical-sector-performance`
  (trailing trend per sector), `biggest-gainers`, `biggest-losers`, `most-active`
  (breadth + froth). ✅ work. **Label these P/Es as NASDAQ-exchange aggregates** —
  they skew high and are valid for *relative* comparison, not as S&P sector multiples.
- **Fundamentals for named equities** (`mcp__claude_ai_FMP__analyst`,
  `…__statements`, `…__discountedCashFlow`): only for names you actually surface.
- **News** (`mcp__claude_ai_FMP__news`): sanity-check headlines if available.

**Known data limits (state these in the report when relevant):**
- `mcp__claude_ai_FMP__quote` (FMP index/commodity/FX/crypto) → **blocked on current
  tier**; use `macro/datafeed.py` instead. Do NOT retry the blocked FMP tool.
- `economics-calendar` / some `economics-indicators` → **blocked on current tier**, so
  the dated catalyst map is unavailable from FMP; say so and flag CPI/Fed/jobs as
  "watch via another source" rather than inventing dates.
- `macro/datafeed.py` gives *levels only* (no trailing history) — VIX is the VIX
  future, DXY the ICE dollar future, Russell the IWM ETF. Note these proxies.

Keep a running note of every figure you retrieve; you will cite them.

## Step 2 — Distill signals (free; reason over what you pulled)

Compute and note, from the retrieved data only:
- **Yield curve**: level, slope (2s10s / 3m10y), and direction of travel. Inverted?
  Steepening? This anchors the regime read.
- **Risk appetite**: VIX level/trend, equity breadth (gainers vs losers, most
  active), credit/curve signals, BTC as a risk proxy.
- **Rotation**: which sectors lead/lag on the snapshot AND over the trailing window;
  is leadership defensive (utilities/staples/healthcare) or cyclical (tech/
  discretionary/industrials)?
- **Valuation extremes**: sector P/E vs its own history — what's stretched, what's
  washed out.
- **Cross-asset divergences**: e.g. gold up + dollar up, oil vs equities, crypto vs
  Nasdaq — note anything that disagrees.
- **Catalyst map**: the dated events from the calendar that fall inside each horizon.

State the **regime call** in one or two sentences (e.g. "late-cycle, curve normalizing
off inversion, defensive leadership, elevated long-end yields") before any ideas.

## Step 3 — Generate output per horizon (three modes)

| Horizon | Mode | Lens |
|---|---|---|
| **Day** | `radar` | what moved last session, what's stretched, what's on watch *right now* |
| **Week** | `trade-book` | catalysts, technicals, positioning, mean-reversion |
| **Month** | `trade-book` | short-term momentum + macro prints |
| **Quarter** | `trade-book` | rate path, earnings season, rotation |
| **Half** (6mo) | `trade-book` | macro regime, mid-cycle rotation |
| **Year** | `trade-book` | valuation + business-cycle position |
| **Multiyear** (2–5yr) | `trade-book` | secular themes, capex/demographics |
| **Lifetime** | `allocation` | asset allocation, NOT stock-picking |

**`radar` mode (Day):** a short tactical brief — the tape (index levels + VIX
regime), what's moving across assets on the session (use `intraday_change_pct`),
what's stretched/froth, the curve state, and an explicit "on watch" list. End with a
one-line "actionable tell." Keep it tight; this is the daily glance.

**`trade-book` mode (Week→Multiyear):** produce **2–4 macro TRADES**, not allocation
advice. A trade is a directional or relative-value *expression*: which asset, long
or short, and against what. Span rates / FX / commodities / equities / vol — not just
"buy an index." Each trade carries: conviction, the expression (incl. a retail
vehicle e.g. futures/FX/options/ETF, noting the ETF is just the wrapper), thesis tied
to retrieved data, catalyst/timing, key risks, and the invalidation condition.

**`allocation` mode (Lifetime):** a diversified, low-cost allocation FRAMEWORK with
percentage ranges across global equities / bonds / real assets, justified by the data
(real yields, valuation dispersion, inflation signal). Be explicit that concentrated
bets are inappropriate here and that the biggest levers are low fees, broad
diversification, staying invested, and DCA. **Ask for / note the personal inputs**
that change the answer (age, time horizon, risk tolerance, income stability, taxes);
present ranges and flag that true personalization needs those.

## Output

Always lead with the regime call, then render each selected horizon in its mode.

```
═══════════════════════════════════════════════
 MACRO SCAN — <date>   |   horizons: <selected>
 Regime: <one-line regime call>
═══════════════════════════════════════════════
```

**radar (Day):**
```
▌ RIGHT NOW (<date>)
  Tape       : <index levels + VIX regime, one line>
  Moving     : <biggest cross-asset movers on the session, with %>
  Stretched  : <what's extended / froth signals>
  Curve      : <slope + direction, one line>
  On watch   : <2–4 specific things to monitor; flag the calendar gap>
  Tell       : <one-line actionable takeaway>
```

**trade-book (Week→Multiyear):**
```
▌ HORIZON: <name> (<span>) — TRADE BOOK
  1. <Trade, e.g. "Long gold / short USD">   ·  conviction: High/Med/Low
     Expression : <direction + instrument/vehicle>
     Thesis     : <why, tied to specific retrieved data>
     Catalyst   : <what makes it play out, and when>
     Key risks  : <what could go wrong>
     Invalidated if: <the specific condition that kills the trade>
  2. ...
```

**allocation (Lifetime):**
```
▌ LONG-TERM ALLOCATION (multi-decade)
  - Global equities  ~XX–XX%  — <rationale from data>
  - Bonds            ~XX–XX%  — <rationale from data>
  - Real assets      ~XX–XX%  — <rationale from data>
  Mechanics: low fees · broad diversification · DCA · rebalance · stay invested.
  Personalize: depends on age / horizon / risk / income / taxes — note what's needed.
```

Close every run with:
- **Top 3 takeaways** (highest-signal observations across the selected horizons).
- **On watch** (dated catalysts if available; otherwise flag the calendar as a gap).
- Disclaimer line, verbatim:
  `Research only — not investment advice. Public data; verify before acting. You bear all risk.`

## Efficiency notes

- Do data collection in as few batched calls as possible; don't re-pull the same
  endpoint. Pull once, reason many times.
- Skip data a selected horizon doesn't need (e.g. don't fetch DCFs for a week-only run).
- Spend the model's effort on synthesis and risk framing, not on restating raw tables.
