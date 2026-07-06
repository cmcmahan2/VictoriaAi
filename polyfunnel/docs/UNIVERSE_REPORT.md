# POLYFUNNEL universe report

Generated 2026-07-06T22:56:22+00:00 — LIVE DATA

API checks: `{"clob_time": true, "gamma_markets_ok": true, "clob_book_ok": true, "fee_rate_sample": true}`

Active markets scanned: **46816** (of which 4358 are past their endDate but not closed — 'zombies'; they stay in the table but rank low on vol24)

Universe rows written to `data/universe.ndjson.gz` (gitignored, local only).

## Buckets by 24h volume

| bucket | n | vol24 sum | vol24 med | spread med | liq med | recurring | underlying |
|---|---|---|---|---|---|---|---|
| cat_sports | 21560 | 65,637,197 | 0 | 0.620 | 89 | N | N |
| sports_game | 8915 | 32,314,840 | 0 | 0.960 | 10 | Y | N |
| cat_unknown | 1319 | 8,509,478 | 9 | 0.020 | 8,366 | N | N |
| cat_politics | 3894 | 5,627,761 | 0 | 0.010 | 14,328 | N | N |
| econ_print | 204 | 5,242,507 | 21 | 0.017 | 4,754 | Y | N |
| cat_crypto | 2921 | 4,051,622 | 0 | 0.020 | 1,395 | N | N |
| cat_weather | 1448 | 2,894,376 | 940 | 0.005 | 4,222 | N | N |
| cat_culture | 1316 | 1,495,752 | 0 | 0.037 | 1,169 | N | N |
| cat_tech | 538 | 851,323 | 23 | 0.010 | 5,872 | N | N |
| cat_finance_prices | 1459 | 844,819 | 8 | 0.040 | 874 | N | N |
| crypto_btc_updown | 489 | 148,738 | 0 | 0.010 | 13,886 | Y | Y |
| cat_economics | 469 | 88,555 | 0 | 0.027 | 2,928 | N | N |
| cat_general | 114 | 74,443 | 0 | 0.130 | 444 | N | N |
| crypto_eth_updown | 457 | 33,845 | 0 | 0.010 | 6,317 | Y | Y |
| cat_mentions | 410 | 16,567 | 0 | 0.760 | 43 | N | N |
| crypto_alt_updown | 1303 | 13,957 | 0 | 0.010 | 2,210 | Y | Y |

## Live fee schedule observed (Gamma `feeSchedule.rate` by `feeType`)

| feeType | rate | n markets |
|---|---|---|
| sports_fees_v2 | 0.030 | 30385 |
| crypto_fees_v2 | 0.070 | 5169 |
| politics_fees | 0.040 | 3898 |
| finance_prices_fees | 0.040 | 1467 |
| weather_fees | 0.050 | 1448 |
| (none) | — | 1323 |
| culture_fees | 0.050 | 1316 |
| economics_fees | 0.050 | 669 |
| tech_fees | 0.040 | 538 |
| mentions_fees | 0.040 | 488 |
| general_fees | 0.050 | 114 |
| crypto_15_min | 0.250 | 1 |

## Top recurring series by 24h volume (Gamma `/series`)

| series | recurrence | vol24 |
|---|---|---|
| soccer-fifwc | daily | 199,318,418 |
| btc-up-or-down-5m | 5m | 24,126,110 |
| wimbledon | daily | 17,169,344 |
| league-of-legends | daily | 11,357,196 |
| mlb | daily | 6,720,872 |
| fomc | monthly | 4,876,486 |
| btc-up-or-down-15m | 15m | 3,197,849 |
| btc-multi-strikes-weekly | daily | 2,793,444 |
| eth-up-or-down-5m | 5m | 2,431,367 |
| atp | daily | 1,785,479 |
| wta | daily | 1,538,166 |
| hormuz-traffic-returns-to-normal | monthly | 1,509,807 |
| counter-strike | daily | 1,422,838 |
| elon-tweets | weekly | 1,239,796 |
| valorant | daily | 1,170,081 |
