# GROUND_TRUTH — Polymarket APIs, fees, and constraints

Compiled 2026-07-06. Every claim carries a verification status:

- **[SOURCE]** — verified from official client source code installed from PyPI (py-clob-client v0.34.6). Highest confidence available in this environment.
- **[DOC]** — cross-checked across ≥2 documentation/analysis sources via web search; dated URLs below. Not runtime-verified.
- **[LIVE]** — runtime-verified against the production APIs on the date noted. Highest confidence.
- **[UNVERIFIED]** — needs a live API call. `scripts/phase0_recon.py` performs all runtime verification and stamps `config/costs.yaml` when it succeeds.

> **Environment status (updated 2026-07-06, retry session).** The network policy now allowlists `*.polymarket.com` — live probes and `phase0_recon.py` work. It does **not** allowlist PyPI/npm (`x-deny-reason: host_not_allowed`), so third-party packages (httpx, polars, pyarrow, ccxt…) cannot be installed here; the API clients fall back to a stdlib HTTP shim (`src/polyfunnel/api/_compat.py`) and recon aggregates without polars (universe written as `data/universe.ndjson.gz` instead of parquet). Exchange APIs for ccxt remain unprobed from this container. Fee and taxonomy claims below marked [LIVE 2026-07-06] were verified in this session.

## 1. API surface

### Gamma API — market/event metadata catalog
- Base: `https://gamma-api.polymarket.com` **[LIVE 2026-07-06]**
- `GET /markets` — pagination via `limit` + `offset`; filters `active`, `closed`, `order`, `ascending`, `end_date_min`/`end_date_max` (inclusive) **[LIVE 2026-07-06]**
  - **`limit` is capped at 100** (docs still say 500; larger values are silently truncated to 100). **[LIVE 2026-07-06]**
  - **`offset` > 2000 returns 422** `"offset too large, use /markets/keyset"`, but `/markets/keyset`'s `next_cursor` is not accepted back via any obvious query param (`cursor`/`next_cursor`/`after` all ignored, garbage values not rejected). Full enumeration: order by `endDate` ascending and advance `end_date_min` windows, dedupe on id — implemented in `GammaClient.iter_markets`. **[LIVE 2026-07-06]**
  - `GET /markets` returns `category: null` on live data; the server-side taxonomy now lives in `feeType` (`crypto_fees_v2`, `sports_fees_v2`, `politics_fees`, …) and `feeSchedule` per market. **[LIVE 2026-07-06]**
  - `active=true&closed=false` includes "zombie" markets whose `endDate` is months in the past (e.g. stale politics markets from 2025-10) — filter/flag on `endDate` explicitly. **[LIVE 2026-07-06]**
  - `?id=<id>` returns `[]` for recent market ids (~2.8M range) while working for old ones — look markets up **by slug**. **[LIVE 2026-07-07]**
  - Settled markets disappear from the default (`closed=false`-behaving) listing; query with `closed=true` to retrieve them (`outcomePrices` become exact `"1"`/`"0"`). **[LIVE 2026-07-07]**
  - 5m up/down settlement (exact outcomePrices + closed=true) lags the window end by **~6–30 minutes**; in the interim the market shows near-terminal prices (e.g. 0.005/0.995) with `closed=false`. Outcome capture must poll patiently — handled in `scripts/collect_updown.py`. **[LIVE 2026-07-07]**
- `GET /events` — event-level (an event page contains ≥1 markets); common discovery: `?active=true&closed=false&order=volume24hr&ascending=false` **[DOC]**
- Also: `/series`, `/tags`, `/search` **[DOC]**
- No auth for reads. Cache-Control headers 30–60s — honor them. **[DOC]**
- Rate limits: Cloudflare throttling; ~60 req/min unauthenticated is the safe documented figure; empirically ~30 req/s tolerated, 429s retry-safe. Our clients pace at 2 req/s. **[DOC]**

### CLOB API — books, prices, history, orders
- Base: `https://clob.polymarket.com` **[SOURCE]**
- Public reads (no auth) **[SOURCE — endpoint paths from py-clob-client v0.34.6 `endpoints.py`]**:
  `/time`, `/book`, `/books`, `/price`, `/prices`, `/midpoint(s)`, `/spread(s)`, `/tick-size`, `/fee-rate`, `/last-trade-price`, `/markets`, `/simplified-markets`, `/sampling-markets`, `/neg-risk`
- `GET /prices-history?market=<token_id>` — `interval` OR `startTs`/`endTs` (mutually exclusive); `fidelity` = bucket size in minutes, **advisory**. Returns `{"history": [{t, p}]}`. **[LIVE 2026-07-06]**
  - **Critical granularity constraint [DOC]:** for older/resolved markets, sub-12-hour fidelity frequently returns *empty* (e.g. `fidelity=60` empty while `fidelity=720` works — py-clob-client issues #189, #216). Fine-grained history is only reliably obtainable by collecting it live. **This is why Phase 1 collectors start on day one.**
  - Live check: `interval=1h&fidelity=1` on an active btc-updown-5m token returned 61 points (~1/min) — minute granularity works on live markets; the constraint above applies to historical/resolved ones. **[LIVE 2026-07-06]**
- Auth model **[SOURCE]**: L1 = Polygon private key signs order structs; L2 = derived API key/secret/passphrase (`/auth/derive-api-key`, `/auth/api-key`). Read-only API keys exist (`/auth/readonly-api-key`). Order endpoints: `POST /order`, `POST /orders`, cancels, `/orders-scoring`.
- **Fee enforcement at order level [SOURCE]:** `create_order` resolves the market's `fee_rate_bps` via `GET /fee-rate` and *rejects* user-supplied mismatches (`client.py:477-490`). Fees are per-market and dynamic — the executor and backtester must both read them at runtime.

### WebSocket — live market data
- `wss://ws-subscriptions-clob.polymarket.com/ws/market` **[DOC]**
- Subscribe: `{"assets_ids": ["<token_id>", ...], "type": "market", "custom_feature_enabled": true}` **[DOC]**
- Events: initial `book` snapshot, then `price_change`, `tick_size_change`, `last_trade_price`; with custom features also `best_bid_ask`, `new_market`, `market_resolved` **[DOC]**
- Keepalive: send PING every 10s; reply PONG within 10s or the server closes. **[DOC]**
- There is also a separate real-time data service (RTDS) used by the site; the CLOB market channel above is the documented public path. **[DOC]**

### Data-API
- `https://data-api.polymarket.com` — holders/positions/activity analytics. Lower priority for us. **[DOC, UNVERIFIED]**

### RTDS — the resolution feed relay (critical for 5m up/down)
- 5m up/down markets resolve on the **Chainlink BTC/USD data stream** — confirmed verbatim in live market rules, which disclaim "other sources or spot markets". **Ties (flat window) resolve Up** ("greater than or equal to"). **[LIVE 2026-07-07]**
- `wss://ws-live-data.polymarket.com` (no auth) relays that exact feed: topic `crypto_prices_chainlink` (symbols like `btc/usd`) = resolution feed / strike capture; topic `crypto_prices` (symbols like `btcusdt`) = Binance-sourced leading feed. Subscribe: `{"action":"subscribe","subscriptions":[{"topic":...,"type":"*","filters":"{\"symbol\":\"btc/usd\"}"}]}` — note `filters` is a JSON **string**. PING every 5s. **[DOC + official TS client; host FIREWALLED in this sandbox — collector `scripts/collect_rtds.py` runs locally]**
- 5m slugs are deterministic: `btc-updown-5m-<unix_ts>` with ts divisible by 300 (window end). **[LIVE 2026-07-07]**
- Fee/rebate regime (user research 2026-07-07, `vault/research/`): taker fees on crypto since Jan 6 2026; maker rebates = 20% of crypto taker fees, pro-rata by **filled** maker fee-equivalent, daily; **Taker Rebate Program since May 28 2026** — 30-day weighted-volume tiers, crypto weighted 2.3×, refunds 12–50% of taker fees (effective crypto fee at top tier ≈ 0.035·p(1−p)). Community consensus: post-fee profitability migrated to **maker-side execution**. **[DOC — verify tiers live before relying]**

## 2. Fee structure (Fee Structure V2, effective 2026-03-30)

**Formula [DOC, cross-checked 3 sources]:**

```
taker_fee_usdc = shares × base_rate × p × (1 − p)      maker_fee = 0
```

Bell curve, max at p=0.5, symmetric (30¢ trade costs the same as 70¢).

| Category (`feeType`) | base_rate | rebate | max per 100 shares (p=.5) | status |
|---|---|---|---|---|
| Crypto `crypto_fees_v2` (incl. 5-min up/down) | **0.07** | 0.20 | $1.75 | **[LIVE 2026-07-06]** |
| Sports `sports_fees_v2` | **0.03** | 0.25 | $0.75 | **[LIVE 2026-07-06]** |
| Politics `politics_fees` | **0.04** | 0.25 | $1.00 | **[LIVE 2026-07-06]** |
| Economics `economics_fees` | **0.05** | — | $1.25 | **[LIVE 2026-07-06]** |
| Finance / Mentions / Tech / General | 0.04 | — | $1.00 | [DOC] |
| Culture / Weather / Other | 0.05 | — | $1.25 | [DOC] |
| Fee-free (`feesEnabled: false`, incl. geopolitics-type) | **0** | — | $0 | **[LIVE 2026-07-06]** |

- **0.07-vs-0.072 discrepancy: RESOLVED → 0.07.** Verified on a live 5-minute BTC up/down market (`btc-updown-5m-1783377600`): `feeSchedule = {"exponent": 1, "rate": 0.07, "takerOnly": true, "rebateRate": 0.2}`. The 0.072 figure from one secondary source does not appear anywhere live. **[LIVE 2026-07-06]**
- **`GET /fee-rate` returns `{"base_fee": <bps>}` and it is NOT the category rate.** Observed: `base_fee = 1000` for fee-enabled markets in *both* crypto (0.07) and sports (0.03) categories; `base_fee = 0` for a `feesEnabled: false` market. Gamma's per-market `feeSchedule.rate` carries the category rate; `base_fee = 1000` matches Gamma's `takerBaseFee`/`makerBaseFee` fields and is what the signed order's `feeRateBps` must equal (the client-side mismatch rejection in py-clob-client checks this value). Working interpretation: `base_fee` is the order-protocol fee bound, `feeSchedule.rate × p × (1−p)` is the economic taker fee. **Reconcile against actually-charged fees on real fills in Phase 6 before trusting for money decisions.** **[LIVE 2026-07-06, interpretation flagged]**
- `feeSchedule.exponent = 1` on all observed markets → fee curve is exactly `rate × p(1−p)`, confirming the documented formula shape. **[LIVE 2026-07-06]**
- Rollout history: crypto 15-min markets first (Jan 2026), sports (Feb 18), ten categories from Mar 30, 2026. **[DOC]**
- Makers pay zero (`takerOnly: true` live); rebate share is per-category (`rebateRate` 0.20 crypto / 0.25 sports+politics live). **[LIVE 2026-07-06]**
- **Strategic implication:** Polymarket introduced the *highest* fees on short-horizon crypto markets explicitly to break latency arbitrage against spot feeds. Family A (underlying-leads-market) is fighting a fee wall designed against it — it must clear ~$1.75/100sh round-trip at mid prices. Family B/E in geopolitics-adjacent or maker-side executions look structurally cheaper. Maker-side execution (zero fee + rebates) is a first-class design axis for every family, not an afterthought.

## 3. Other frictions
- Trading is relayer-based/gasless for orders (operator pays Polygon gas). **[DOC, UNVERIFIED]**
- Redemption of resolved positions: relayer-covered in-app; direct contract calls cost Polygon gas (negligible, ~<$0.01). **[DOC, UNVERIFIED]**
- Withdrawals: Polygon gas, negligible. **[UNVERIFIED]**
- Tick size: per-market via `GET /tick-size` (typ. 0.01; 0.001 near price extremes). **[SOURCE endpoint / DOC values]**
- Resolution timestamps are ET-anchored (e.g. "up or down at 3pm ET"); normalize everything to UTC with explicit `zoneinfo` conversion. **[DOC + project convention]**

## 4. Market taxonomy — status: LIVE-SCANNED 2026-07-06
`scripts/phase0_recon.py` enumerates active markets, buckets them (crypto up/down recurrers, sports, econ prints, politics, culture), computes per-bucket volume/spread/liquidity/recurrence, writes the universe file under `data/`, and generates `docs/UNIVERSE_REPORT.md` — **see that report for the live ranking table.** Live structural findings **[LIVE 2026-07-06]**:

- **Crypto up/down recurrence is now 5-minute**, not 15-minute: series `btc-up-or-down-5m` (~$24M vol/24h) and `eth-up-or-down-5m` (~$2.4M), plus `btc-up-or-down-15m` (~$3.2M). Slug format is `btc-updown-5m-<unix_ts>` (period-end epoch). A new market every 5 minutes = ~288 BTC markets/day — enormous variant sample sizes for Phase 3, and collectors must auto-discover new tokens continuously (`GET /events?series_slug=btc-up-or-down-5m&end_date_min=<now>`).
- Gamma `/series` exposes `recurrence` directly (`5m`, `15m`, `daily`, `monthly`) — cleaner recurrence source than slug regexes; report includes the top-15 series table.
- Sports game markets dominate headline volume in-season (FIFA World Cup 2026 + Wimbledon + MLB while scanning).
- Zombie markets (past `endDate`, still `active=true&closed=false`) pollute naive scans — flagged per-row as `expired`. 2026-07-06 scan: 4,358 of 46,816 (9.3%).
- **Market-level 24h volume understates recurrer series.** Resolved 5m/15m markets flip to `closed=true` and drop out of an active-market scan, so the `crypto_btc_updown` bucket sums to only ~$149k vol24 while the `btc-up-or-down-5m` *series* reports ~$24M vol24. For recurrence buckets, Gamma `/series` volume is authoritative; the per-market scan measures the standing (active) book only. **[LIVE 2026-07-06]**
- Fee-table anomaly seen in the wild: one zombie market (`xrp-updown-5m-1771916400`, expired, zero volume) carries feeType `crypto_15_min` with rate **0.25** — a legacy artifact. Reinforces the rule: never hardcode category fee tables; fetch per-market at runtime. **[LIVE 2026-07-06]**

## 5. Sources
- https://docs.polymarket.com/trading/fees · https://docs.polymarket.com/polymarket-learn/trading/fees (fee formula, V2 schedule)
- https://docs.polymarket.com/quickstart/introduction/rate-limits (rate limits)
- https://docs.polymarket.com/market-data/websocket/market-channel (WS market channel)
- https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/ (dynamic-fee rationale)
- https://startpolymarket.com/learn/polymarket-fees/ · https://marketmath.io/blog/polymarket-fees-explained · https://www.predictionhunt.com/blog/polymarket-fees-complete-guide (fee tables, cross-checks)
- https://github.com/Polymarket/py-clob-client/issues/189 · /issues/216 (prices-history granularity limits)
- py-clob-client v0.34.6 source from PyPI (endpoints, auth, fee enforcement) — **[SOURCE]**
- https://pm.wiki/learn/polymarket-api · https://www.parlay.run/polymarket-api (endpoint/pagination details)

All web-derived claims accessed 2026-07-06 via search; re-verify at runtime with `phase0_recon.py` before trusting for money decisions.
