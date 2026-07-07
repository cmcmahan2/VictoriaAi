"""
wheel.py — backtest the wheel strategy (sell puts -> get assigned -> sell calls ->
called away -> repeat), collecting premium at every step.

No look-ahead: every DECISION (which strike/expiry to sell) uses only data up to
that day; a contract then resolves on the ACTUAL price at its expiry (that's the
contract settling, not peeking). Premiums are MODELED with Black-Scholes from
recent realized vol — see options.py; real fills differ (IV, spread, skew), so
treat the premium income as an estimate.

    python wheel.py --source synthetic --days 504
    python wheel.py --source alpaca --ticker AAPL --days 730   # needs Alpaca keys, run locally
"""
from __future__ import annotations

import argparse

import config
from data import get_daily
from options import annualized_vol, bs_price

SHARES_PER = 100


def run_wheel(bars, cfg=config):
    closes = [b.close for b in bars]
    r = cfg.RISK_FREE
    qty = SHARES_PER * cfg.CONTRACTS
    T = cfg.EXPIRY_DAYS / 252.0

    cash = cfg.START_CAPITAL
    shares = 0
    cost_basis = 0.0                 # effective per-share cost (net of premium)
    open_c = None                    # {kind,strike,expiry_idx,premium,entry_idx}
    total_premium = 0.0
    trades, equity = [], []
    n_puts = n_calls = n_assigned = n_called = n_closed_early = 0

    start = max(cfg.VOL_LOOKBACK + 1, 1)
    for i in range(start, len(bars)):
        S = closes[i]
        sigma = annualized_vol(closes[:i + 1], cfg.VOL_LOOKBACK)

        # ---- manage an open short option ----
        if open_c:
            t_rem = max(0.0, (open_c["expiry_idx"] - i) / 252.0)
            cur_val = bs_price(S, open_c["strike"], t_rem, r, sigma, open_c["kind"]) * qty
            # early profit-take: buy it back once it's cheap
            if cur_val <= (1 - cfg.PROFIT_TAKE) * open_c["premium"] and i < open_c["expiry_idx"]:
                cash -= cur_val + cfg.FEE_PER_CONTRACT * cfg.CONTRACTS
                trades.append((bars[i].ts, f"close {open_c['kind']} @{open_c['strike']:.0f}",
                               open_c["premium"] - cur_val))
                n_closed_early += 1
                open_c = None
            elif i >= open_c["expiry_idx"]:
                k = open_c["kind"]; strike = open_c["strike"]
                if k == "put":
                    if S < strike:                                   # assigned
                        cash -= strike * qty
                        shares += qty
                        cost_basis = strike - open_c["premium"] / qty
                        n_assigned += 1
                        trades.append((bars[i].ts, f"ASSIGNED {qty}@{strike:.0f}", 0.0))
                    else:
                        trades.append((bars[i].ts, f"put expired worthless @{strike:.0f}", open_c["premium"]))
                else:  # call
                    if S > strike:                                   # called away
                        cash += strike * qty
                        gain = (strike - cost_basis) * qty
                        shares -= qty
                        n_called += 1
                        trades.append((bars[i].ts, f"CALLED AWAY {qty}@{strike:.0f}", gain))
                    else:
                        trades.append((bars[i].ts, f"call expired worthless @{strike:.0f}", open_c["premium"]))
                open_c = None

        # ---- open a new short option if flat on contracts ----
        if open_c is None:
            if shares == 0:                                          # sell cash-secured put
                strike = round(S * (1 - cfg.PUT_STRIKE_PCT), 2)
                if strike * qty <= cash:                             # must be cash-secured
                    prem = bs_price(S, strike, T, r, sigma, "put") * (1 - cfg.SLIPPAGE_PCT) * qty
                    prem -= cfg.FEE_PER_CONTRACT * cfg.CONTRACTS
                    if prem > 0:
                        cash += prem; total_premium += prem; n_puts += 1
                        open_c = {"kind": "put", "strike": strike, "expiry_idx": i + cfg.EXPIRY_DAYS,
                                  "premium": prem, "entry_idx": i}
            else:                                                    # sell covered call
                strike = round(max(S, cost_basis) * (1 + cfg.CALL_STRIKE_PCT), 2)
                prem = bs_price(S, strike, T, r, sigma, "call") * (1 - cfg.SLIPPAGE_PCT) * qty
                prem -= cfg.FEE_PER_CONTRACT * cfg.CONTRACTS
                if prem > 0:
                    cash += prem; total_premium += prem; n_calls += 1
                    open_c = {"kind": "call", "strike": strike, "expiry_idx": i + cfg.EXPIRY_DAYS,
                              "premium": prem, "entry_idx": i}

        # ---- mark-to-market net liquidation value ----
        liab = 0.0
        if open_c:
            t_rem = max(0.0, (open_c["expiry_idx"] - i) / 252.0)
            liab = bs_price(S, open_c["strike"], t_rem, r, sigma, open_c["kind"]) * qty
        equity.append((bars[i].ts, cash + shares * S - liab))

    final = equity[-1][1] if equity else cfg.START_CAPITAL
    bh = cfg.START_CAPITAL / closes[start] * closes[-1]
    peak = equity[0][1] if equity else 0; mdd = 0.0
    for _, e in equity:
        peak = max(peak, e); mdd = max(mdd, (peak - e) / peak if peak else 0)
    return {
        "final": final, "start": cfg.START_CAPITAL,
        "total_return": final / cfg.START_CAPITAL - 1,
        "buy_hold_return": bh / cfg.START_CAPITAL - 1,
        "premium_collected": total_premium,
        "puts_sold": n_puts, "calls_sold": n_calls, "assigned": n_assigned,
        "called_away": n_called, "closed_early": n_closed_early,
        "max_drawdown": mdd, "trades": trades, "equity": equity,
    }


def main():
    ap = argparse.ArgumentParser(description="Backtest the wheel strategy")
    ap.add_argument("--source", choices=["synthetic", "alpaca"], default="synthetic")
    ap.add_argument("--ticker", default=config.TICKER)
    ap.add_argument("--days", type=int, default=504)
    args = ap.parse_args()
    try:
        bars = get_daily(args.ticker, args.days, source=args.source)
    except RuntimeError as e:
        print(f"  ✗ {e}\n  Sandbox blocks Alpaca — run locally, or use --source synthetic.")
        raise SystemExit(2)

    r = run_wheel(bars, config)
    print("=" * 60)
    print(f" WHEEL BACKTEST — {args.ticker} ({args.source}, {len(bars)} days)")
    print("=" * 60)
    print(f" Start / Final        ${r['start']:,.0f} -> ${r['final']:,.0f}")
    print(f" Total return         {r['total_return']*100:+.1f}%")
    print(f" Buy & hold           {r['buy_hold_return']*100:+.1f}%")
    print(f" Premium collected    ${r['premium_collected']:,.0f}")
    print(f" Puts / Calls sold    {r['puts_sold']} / {r['calls_sold']}")
    print(f" Assigned / Called    {r['assigned']} / {r['called_away']}  (early-closed {r['closed_early']})")
    print(f" Max drawdown         {r['max_drawdown']*100:.1f}%")
    print("-" * 60)
    if args.source == "synthetic":
        print(" !! SYNTHETIC DATA + MODELED PREMIUMS (Black-Scholes) — plumbing, not edge.")
    print(" Premiums are modeled (real IV/spread/skew differ). Paper-trade before real money.")
    print("=" * 60)


if __name__ == "__main__":
    main()
