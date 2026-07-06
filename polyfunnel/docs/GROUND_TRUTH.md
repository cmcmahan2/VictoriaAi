# GROUND_TRUTH — Polymarket APIs, fees, and constraints

Compiled 2026-07-06. Every claim carries a verification status:

- **[SOURCE]** — verified from official client source code installed from PyPI (py-clob-client v0.34.6). Highest confidence available in this environment.
- **[DOC]** — cross-checked across ≥2 documentation/analysis sources via web search; dated URLs below. Not runtime-verified.
- **[UNVERIFIED]** — needs a live API call. `scripts/phase0_recon.py` performs all runtime verification and stamps `config/costs.yaml` when it succeeds.

> ⚠️ **Environment blocker.** This Claude-Code-web container's network policy 403-blocks all outbound HTTPS except package registries (PyPI/npm) and GitHub. Direct probes of `gamma-api.polymarket.com`, `clob.polymarket.com`, `data-api.polymarket.com`, and exchange APIs (Binance/Coinbase for ccxt) all fail at the proxy (`CONNECT tunnel failed, response 403`, logged 2026-07-06). WebSearch works, so this file is documentation-derived where marked. **Nothing here is trusted for backtesting until `phase0_recon.py` runs successfully** — either locally or after widening this environment's network policy (Claude Code on the web → environment settings → network policy).

## 1. API surface

### Gamma API — market/event metadata catalog
- Base: `https://gamma-api.polymarket.com` **[DOC]**
- `GET /markets` — pagination via `limit` (max 500) + `offset`; filters `active`, `closed`, `order`, `ascending` **[DOC]**
- `GET /events` — event-level (an event page contains ≥1 markets); common discovery: `?active=true&closed=false&order=volume24hr&ascending=false` **[DOC]**
- Also: `/series`, `/tags`, `/search` **[DOC]**
- No auth for reads. Cache-Control headers 30–60s — honor them. **[DOC]**
- Rate limits: Cloudflare throttling; ~60 req/min unauthenticated is the safe documented figure; empirically ~30 req/s tolerated, 429s retry-safe. Our clients pace at 2 req/s. **[DOC]**

### CLOB API — books, prices, history, orders
- Base: `https://clob.polymarket.com` **[SOURCE]**
- Public reads (no auth) **[SOURCE — endpoint paths from py-clob-client v0.34.6 `endpoints.py`]**:
  `/time`, `/book`, `/books`, `/price`, `/prices`, `/midpoint(s)`, `/spread(s)`, `/tick-size`, `/fee-rate`, `/last-trade-price`, `/markets`, `/simplified-markets`, `/sampling-markets`, `/neg-risk`
- `GET /prices-history?market=<token_id>` — `interval` OR `startTs`/`endTs` (mutually exclusive); `fidelity` = bucket size in minutes, **advisory**. Returns `[{t, p}]`. **[DOC]**
  - **Critical granularity constraint [DOC]:** for older/resolved markets, sub-12-hour fidelity frequently returns *empty* (e.g. `fidelity=60` empty while `fidelity=720` works — py-clob-client issues #189, #216). Fine-grained history is only reliably obtainable by collecting it live. **This is why Phase 1 collectors start on day one.**
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

## 2. Fee structure (Fee Structure V2, effective 2026-03-30)

**Formula [DOC, cross-checked 3 sources]:**

```
taker_fee_usdc = shares × base_rate × p × (1 − p)      maker_fee = 0
```

Bell curve, max at p=0.5, symmetric (30¢ trade costs the same as 70¢).

| Category | base_rate | max per 100 shares (p=.5) |
|---|---|---|
| Crypto (incl. 15-min/hourly up-down) | 0.07 (one source implies 0.072) | $1.75–$1.80 |
| Sports | 0.03 | $0.75 |
| Finance / Politics / Mentions / Tech | 0.04 | $1.00 |
| Economics / Culture / Weather / Other | 0.05 | $1.25 |
| Geopolitics / world events | **0** | $0 |

- Rollout history: crypto 15-min markets first (Jan 2026), sports (Feb 18), ten categories from Mar 30, 2026. **[DOC]**
- Makers pay zero; 100% of taker fees redistributed to makers, 20–25% daily rebate share. **[DOC]**
- **Strategic implication:** Polymarket introduced the *highest* fees on short-horizon crypto markets explicitly to break latency arbitrage against spot feeds. Family A (underlying-leads-market) is fighting a fee wall designed against it — it must clear ~$1.75/100sh round-trip at mid prices. Family B/E in geopolitics-adjacent or maker-side executions look structurally cheaper. Maker-side execution (zero fee + rebates) is a first-class design axis for every family, not an afterthought.
- Discrepancy to resolve live: 0.07 vs 0.072 crypto rate; per-market `GET /fee-rate` is authoritative. **[UNVERIFIED]**

## 3. Other frictions
- Trading is relayer-based/gasless for orders (operator pays Polygon gas). **[DOC, UNVERIFIED]**
- Redemption of resolved positions: relayer-covered in-app; direct contract calls cost Polygon gas (negligible, ~<$0.01). **[DOC, UNVERIFIED]**
- Withdrawals: Polygon gas, negligible. **[UNVERIFIED]**
- Tick size: per-market via `GET /tick-size` (typ. 0.01; 0.001 near price extremes). **[SOURCE endpoint / DOC values]**
- Resolution timestamps are ET-anchored (e.g. "up or down at 3pm ET"); normalize everything to UTC with explicit `zoneinfo` conversion. **[DOC + project convention]**

## 4. Market taxonomy — status: BLOCKED, script ready
`scripts/phase0_recon.py` enumerates active markets, buckets them (crypto up/down recurrers, sports, econ prints, politics, culture), computes per-bucket volume/spread/liquidity/recurrence, writes `data/universe.parquet`, and generates `docs/UNIVERSE_REPORT.md`. It cannot run in this container (network policy). Expected ranking based on documented structure **[DOC, provisional — do not build on this without the live scan]**:

1. **Crypto up/down recurrers (BTC/ETH 15-min/hourly/daily)** — perfect recurrence, observable underlying (ccxt 1-min candles), continuous liquidity; but highest fee tier and explicitly fee-defended against latency arb.
2. **Sports game markets** — high recurrence and volume, in-play data costly (Family F stays flag-gated).
3. **Econ prints (CPI/FOMC/NFP)** — recurring but low frequency; good vault material.
4. **Politics/culture one-offs** — not backtestable as a class; vault-only, deprioritized for the bot.

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
