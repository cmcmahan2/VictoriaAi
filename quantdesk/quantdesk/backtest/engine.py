"""Event-driven daily backtest loop for CSP / covered-call / wheel.

One underlying, one contract per cycle, no lookahead: every decision at
bar *i* uses only closes[0..i]. Entries and exits fill at that bar's
close-derived synthetic price, always net of slippage and fees.

Modes:
  csp          — sell puts; if assigned, liquidate shares at the
                 settlement close and go back to cash.
  wheel        — sell puts; if assigned, hold and sell covered calls
                 until called away.
  covered-call — buy 100 shares on day one, sell calls forever; if
                 called away, rebuy at the next bar's close.

Every result carries SYNTHETIC_WARNING. Absolute numbers are
approximations; use them to compare regimes, parameters, and strategies
— not to forecast your P&L.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from quantdesk.backtest.costs import CostModel
from quantdesk.backtest.synthetic import (
    MIN_BARS_FOR_IV,
    SYNTHETIC_WARNING,
    strike_for_delta,
    synthetic_iv,
    synthetic_price,
)
from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import OptionType, PriceHistory

BacktestMode = Literal["csp", "wheel", "covered-call"]


class ExitReason(str, Enum):
    TAKE_PROFIT = "take-profit"
    TIME_EXIT = "time-exit"
    STOP_LOSS = "stop-loss"
    EXPIRED = "expired-worthless"
    ASSIGNED = "assigned"
    CALLED_AWAY = "called-away"


class TradeRecord(BaseModel):
    kind: OptionType
    strike: float
    open_date: dt.date
    close_date: dt.date
    expiry: dt.date
    credit_net: float          # $ received at open, net of costs
    close_cost_net: float      # $ paid at close, net of costs (0 if expired)
    pnl: float                 # option-leg P&L only (share P&L is in equity)
    exit_reason: ExitReason


class BacktestResult(BaseModel):
    mode: BacktestMode
    symbol: str
    dates: list[dt.date]
    equity: list[float]
    initial_capital: float
    trades: list[TradeRecord]
    gross_premium: float       # total $ premium sold before costs
    total_costs: float         # fees + slippage, both sides
    warnings: list[str] = Field(default_factory=list)


class _OpenOption(BaseModel):
    kind: OptionType
    strike: float
    expiry: dt.date
    open_date: dt.date
    credit_net: float
    credit_mid: float          # mid price at entry, for exit triggers


def run_backtest(
    history: PriceHistory,
    mode: BacktestMode,
    config: QuantDeskConfig,
    cost_model: CostModel | None = None,
    put_delta_target: float | None = None,
) -> BacktestResult:
    """Run the daily loop over ``history``. Needs >= MIN_BARS_FOR_IV + 2 bars."""
    bars = history.bars
    if len(bars) < MIN_BARS_FOR_IV + 2:
        raise ValueError(
            f"need at least {MIN_BARS_FOR_IV + 2} bars, got {len(bars)}"
        )
    costs = cost_model or CostModel(
        per_contract_fee=config.costs.per_contract_fee,
        commission=config.costs.commission,
    )
    rate = config.data.risk_free_rate
    richness = config.backtest.iv_richness
    exits = config.strategy.exits
    csp_cfg = config.strategy.csp
    target_dte = (csp_cfg.dte_min + csp_cfg.dte_max) // 2
    put_delta = (
        put_delta_target
        if put_delta_target is not None
        else (csp_cfg.delta_min + csp_cfg.delta_max) / 2.0
    )
    call_delta = -put_delta  # mirrored band

    closes = [b.close for b in bars]
    capital = closes[0] * 110.0  # secures one contract at any strike <= 110% spot
    cash = capital
    shares = 0
    open_opt: _OpenOption | None = None

    dates: list[dt.date] = []
    equity: list[float] = []
    trades: list[TradeRecord] = []
    gross_premium = 0.0
    total_costs = 0.0

    def record_costs(mid_value: float, net_value: float) -> None:
        nonlocal total_costs
        total_costs += abs(mid_value - net_value)

    def sell_option(
        kind: OptionType, spot: float, closes_so_far: list[float], today: dt.date
    ) -> _OpenOption:
        nonlocal cash, gross_premium
        iv = synthetic_iv(closes_so_far, richness)
        target = put_delta if kind == "put" else call_delta
        strike = strike_for_delta(kind, spot, target, target_dte, rate, iv)
        mid = synthetic_price(kind, spot, strike, target_dte, rate, iv)
        proceeds = costs.sell_proceeds(mid, spot, strike, target_dte)
        cash += proceeds
        gross_premium += mid * 100.0
        record_costs(mid * 100.0, proceeds)
        return _OpenOption(
            kind=kind,
            strike=strike,
            expiry=today + dt.timedelta(days=target_dte),
            open_date=today,
            credit_net=proceeds,
            credit_mid=mid,
        )

    def close_option(
        opt: _OpenOption, cost_net: float, today: dt.date, reason: ExitReason
    ) -> None:
        trades.append(
            TradeRecord(
                kind=opt.kind,
                strike=opt.strike,
                open_date=opt.open_date,
                close_date=today,
                expiry=opt.expiry,
                credit_net=opt.credit_net,
                close_cost_net=cost_net,
                pnl=opt.credit_net - cost_net,
                exit_reason=reason,
            )
        )

    if mode == "covered-call":
        # Own the shares from the first tradable bar.
        shares = 100
        cash -= closes[MIN_BARS_FOR_IV] * 100.0  # bought at first decision bar

    for i in range(MIN_BARS_FOR_IV, len(bars)):
        bar = bars[i]
        spot = bar.close
        today = bar.date
        closes_so_far = closes[: i + 1]

        if open_opt is not None:
            dte_left = (open_opt.expiry - today).days
            if today >= open_opt.expiry:
                # Settle at expiry on this bar's close.
                itm = (
                    spot < open_opt.strike
                    if open_opt.kind == "put"
                    else spot > open_opt.strike
                )
                if not itm:
                    close_option(open_opt, 0.0, today, ExitReason.EXPIRED)
                    open_opt = None
                elif open_opt.kind == "put":
                    # Assigned: buy 100 shares at strike.
                    cash -= open_opt.strike * 100.0
                    shares = 100
                    close_option(open_opt, 0.0, today, ExitReason.ASSIGNED)
                    open_opt = None
                    if mode == "csp":
                        # CSP mode refuses to hold stock: sell at settlement close.
                        cash += spot * 100.0
                        shares = 0
                else:
                    # Short call assigned: shares called away at strike.
                    cash += open_opt.strike * 100.0
                    shares = 0
                    close_option(open_opt, 0.0, today, ExitReason.CALLED_AWAY)
                    open_opt = None
            else:
                iv = synthetic_iv(closes_so_far, richness)
                mid = synthetic_price(
                    open_opt.kind, spot, open_opt.strike, dte_left, rate, iv
                )
                reason: ExitReason | None = None
                if mid <= open_opt.credit_mid * (1.0 - exits.take_profit_pct):
                    reason = ExitReason.TAKE_PROFIT
                elif mid >= open_opt.credit_mid * (
                    1.0 + exits.stop_loss_credit_multiple
                ):
                    reason = ExitReason.STOP_LOSS
                elif dte_left <= exits.time_exit_dte:
                    reason = ExitReason.TIME_EXIT
                if reason is not None:
                    buyback = costs.buy_cost(mid, spot, open_opt.strike, dte_left)
                    cash -= buyback
                    record_costs(mid * 100.0, buyback)
                    close_option(open_opt, buyback, today, reason)
                    open_opt = None

        # Entries (same bar as an exit is allowed: capital is free again).
        if open_opt is None and i < len(bars) - 1:  # never open on the last bar
            if shares == 0 and mode in ("csp", "wheel"):
                open_opt = sell_option("put", spot, closes_so_far, today)
            elif shares == 100 and mode in ("wheel", "covered-call"):
                open_opt = sell_option("call", spot, closes_so_far, today)
            elif shares == 0 and mode == "covered-call":
                # Called away earlier: rebuy at this bar's close.
                cash -= spot * 100.0
                shares = 100
                open_opt = sell_option("call", spot, closes_so_far, today)

        # Mark to market.
        opt_liability = 0.0
        if open_opt is not None:
            dte_left = max((open_opt.expiry - today).days, 0)
            iv = synthetic_iv(closes_so_far, richness)
            opt_liability = (
                synthetic_price(
                    open_opt.kind, spot, open_opt.strike, dte_left, rate, iv
                )
                * 100.0
            )
        dates.append(today)
        equity.append(cash + shares * spot - opt_liability)

    return BacktestResult(
        mode=mode,
        symbol=history.symbol,
        dates=dates,
        equity=equity,
        initial_capital=capital,
        trades=trades,
        gross_premium=gross_premium,
        total_costs=total_costs,
        warnings=[SYNTHETIC_WARNING],
    )


class WalkForwardResult(BaseModel):
    best_delta: float
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    overfit_flag: bool
    detail: str


def walk_forward(
    history: PriceHistory,
    mode: BacktestMode,
    config: QuantDeskConfig,
    split_date: dt.date,
    delta_grid: tuple[float, ...] = (-0.20, -0.25, -0.30),
) -> WalkForwardResult:
    """Pick the delta target in-sample, validate out-of-sample.

    Overfit flag: OOS Sharpe < 50% of in-sample Sharpe (spec threshold).
    A flagged result means the parameter choice fit noise — do not trade it.
    """
    from quantdesk.backtest.metrics import daily_returns, sharpe

    in_bars = [b for b in history.bars if b.date < split_date]
    out_bars = [b for b in history.bars if b.date >= split_date]
    if len(in_bars) < MIN_BARS_FOR_IV + 10 or len(out_bars) < MIN_BARS_FOR_IV + 10:
        raise ValueError("not enough data on one side of the split")

    in_hist = PriceHistory(symbol=history.symbol, bars=in_bars)
    out_hist = PriceHistory(symbol=history.symbol, bars=out_bars)

    best_delta = delta_grid[0]
    best_is_sharpe = float("-inf")
    for d in delta_grid:
        res = run_backtest(in_hist, mode, config, put_delta_target=d)
        s = sharpe(daily_returns(res.equity))
        if s > best_is_sharpe:
            best_is_sharpe = s
            best_delta = d

    oos = run_backtest(out_hist, mode, config, put_delta_target=best_delta)
    oos_sharpe = sharpe(daily_returns(oos.equity))
    overfit = (
        best_is_sharpe > 0 and oos_sharpe < 0.5 * best_is_sharpe
    )
    return WalkForwardResult(
        best_delta=best_delta,
        in_sample_sharpe=best_is_sharpe,
        out_of_sample_sharpe=oos_sharpe,
        overfit_flag=overfit,
        detail=(
            f"delta {best_delta:+.2f} chosen on data before {split_date}; "
            f"IS Sharpe {best_is_sharpe:.2f} vs OOS {oos_sharpe:.2f}"
            + (" — OVERFIT (OOS < 50% of IS)" if overfit else "")
        ),
    )
