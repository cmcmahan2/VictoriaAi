"""QuantDesk dashboard — read-only view over the same SQLite DB.

Run with:  streamlit run quantdesk/dashboard.py
       or: quantdesk dashboard

Four tabs: Scanner, Portfolio, Journal, Regime. The CLI remains the
workhorse; this is for looking, not deciding. Nothing here executes
trades or writes to the journal.

Every tab is wrapped in its own error boundary: yfinance being down (or
this machine being offline) degrades that tab to an error banner instead
of killing the page — the Journal tab works fully offline.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from quantdesk.analytics.regime import classify_regime
from quantdesk.config import QuantDeskConfig, load_config
from quantdesk.data.provider import YFinanceProvider
from quantdesk.journal.models import Journal, TradeStatus
from quantdesk.journal.review import monthly_review
from quantdesk.risk.portfolio import correlation_matrix
from quantdesk.screener.universe import scan_universe
from quantdesk.strategies.csp import CashSecuredPut


def _provider(config: QuantDeskConfig) -> YFinanceProvider:
    return YFinanceProvider(
        db_path=config.db_path,
        quote_ttl=config.data.quote_cache_ttl_seconds,
        chain_ttl=config.data.chain_cache_ttl_seconds,
        history_ttl=config.data.history_cache_ttl_seconds,
    )


@st.cache_data(ttl=15 * 60, show_spinner="Scanning universe…")
def _cached_scan() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    config = load_config()
    ranked, excluded, note = scan_universe(_provider(config), config)
    rows = []
    for r in ranked:
        m = r.metrics
        assert m is not None and m.best_strike is not None and r.score is not None
        b = m.best_strike
        rows.append(
            {
                "symbol": m.symbol,
                "strike": b.contract.strike,
                "delta": round(b.delta, 2),
                "DTE": m.dte,
                "credit": round(b.mid, 2),
                "ann.yield": f"{b.annualized_yield:.1%}",
                "IV rank": f"{m.iv_rank:.0f} ({m.iv_rank_source})",
                "VRP": f"{m.vrp:+.1%}",
                "OI": b.open_interest,
                "spread": f"{b.spread_pct:.1%}" if b.spread_pct is not None else "—",
                "score": round(r.score.total, 2),
            }
        )
    excl = [
        {"symbol": r.symbol, "reasons": "; ".join(r.exclusion_reasons)}
        for r in excluded
    ]
    return rows, excl, note


def scanner_tab() -> None:
    st.caption(
        "Ranked CSP candidates from the config watchlist. Estimates throughout; "
        "chains cached 15 min."
    )
    if st.button("Run scan (uses live data)"):
        _cached_scan.clear()
    rows, excluded, note = _cached_scan()
    st.text(f"per-position cap: {note}")
    if rows:
        st.dataframe(rows, width="stretch")
        pick = st.selectbox("Proposals for…", [r["symbol"] for r in rows])
        if pick:
            _show_proposals(str(pick))
    else:
        st.warning("No symbol passed every filter — a valid answer, not a bug.")
    with st.expander(f"{len(excluded)} excluded — every reason queryable"):
        st.dataframe(excluded, width="stretch")


def _show_proposals(symbol: str) -> None:
    from quantdesk.screener.universe import select_expiry

    config = load_config()
    provider = _provider(config)
    expiry = select_expiry(
        provider.get_expirations(symbol),
        config.strategy.csp.dte_min,
        config.strategy.csp.dte_max,
    )
    if expiry is None:
        st.error("No expiry in the DTE band.")
        return
    chain = provider.get_option_chain(symbol, expiry)
    div_yield = provider.get_dividend_yield(symbol)
    for p in CashSecuredPut().propose(chain, config, div_yield)[:3]:
        with st.container(border=True):
            st.markdown(
                f"**SELL {p.underlying} {p.legs[0].contract.strike:g}p "
                f"{p.expiry} ({p.dte} DTE)** — credit ~{p.net_credit:.2f}"
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("POP (model)", f"{p.pop_model:.0%}")
            c2.metric("Ann. yield", f"{p.annualized_yield_on_collateral:.1%}")
            c3.metric("Collateral", f"${p.collateral:,.0f}")
            c4.metric("Max loss", f"${p.max_loss:,.0f}")
            st.caption(" · ".join(p.exit_plan.rules))
            for w in p.warnings:
                st.warning(w)


def portfolio_tab() -> None:
    config = load_config()
    journal = Journal(config.db_path)
    open_trades = journal.list_trades(TradeStatus.OPEN)
    if not open_trades:
        st.info("No open positions in the journal.")
        return
    st.dataframe(
        [
            {
                "id": t.id,
                "symbol": t.symbol,
                "strategy": t.strategy,
                "opened": t.opened_at.isoformat(),
                "credit $": t.credit_total,
                "strike": t.legs[0].strike if t.legs else None,
                "expiry": t.legs[0].expiry.isoformat() if t.legs else None,
                "override": "YES" if t.override_used else "",
            }
            for t in open_trades
        ],
        width="stretch",
    )
    deployed = sum(
        t.legs[0].strike * 100 * t.legs[0].contracts for t in open_trades if t.legs
    )
    cap = config.account.size * config.risk.max_deployed_pct
    st.progress(
        min(deployed / cap, 1.0) if cap > 0 else 0.0,
        text=f"collateral deployed ~${deployed:,.0f} vs cap ${cap:,.0f} "
        f"({config.account.currency} account — FX applied at proposal time)",
    )
    symbols = sorted({t.symbol for t in open_trades})
    if len(symbols) >= 2:
        st.subheader("90d correlation heatmap")
        try:
            provider = _provider(config)
            close_map = {
                s: provider.get_price_history(s).closes for s in symbols
            }
            matrix = correlation_matrix(
                {k: v for k, v in close_map.items()}, window=90
            )
            z = [
                [
                    1.0 if a == b else matrix.get((min(a, b), max(a, b)), 0.0)
                    for b in symbols
                ]
                for a in symbols
            ]
            fig = go.Figure(
                go.Heatmap(z=z, x=symbols, y=symbols, zmin=-1, zmax=1,
                           colorscale="RdBu", reversescale=True)
            )
            st.plotly_chart(fig, width="stretch")
        except Exception as exc:  # pragma: no cover - needs live data
            st.error(f"correlation data unavailable: {exc}")


def journal_tab() -> None:
    config = load_config()
    journal = Journal(config.db_path)
    trades = journal.list_trades()
    if not trades:
        st.info("Journal is empty. Log fills with `quantdesk journal open …`.")
        return
    closed = [
        t for t in trades
        if t.status == TradeStatus.CLOSED and t.closed_at and t.realized_pnl is not None
    ]
    if closed:
        closed.sort(key=lambda t: t.closed_at or dt.date.min)
        dates = [t.closed_at for t in closed]
        cum: list[float] = []
        total = 0.0
        for t in closed:
            total += t.realized_pnl or 0.0
            cum.append(total)
        fig = go.Figure(go.Scatter(x=dates, y=cum, mode="lines+markers"))
        fig.update_layout(title="Cumulative realized P&L ($)", height=300)
        st.plotly_chart(fig, width="stretch")
    st.dataframe(
        [
            {
                "id": t.id, "symbol": t.symbol, "strategy": t.strategy,
                "status": t.status.value, "opened": t.opened_at.isoformat(),
                "closed": t.closed_at.isoformat() if t.closed_at else "—",
                "P&L": t.realized_pnl, "exit": t.exit_reason or "—",
                "override": "YES" if t.override_used else "",
            }
            for t in trades
        ],
        width="stretch",
    )
    st.subheader("Monthly review")
    today = dt.date.today()
    month = st.text_input("Month (YYYY-MM)", value=today.strftime("%Y-%m"))
    try:
        year_s, mon_s = month.split("-")
        r = monthly_review(journal, int(year_s), int(mon_s))
    except Exception:
        st.error("Use YYYY-MM.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P&L", f"{r.total_pnl:+,.0f}")
    c2.metric("Win rate", f"{r.win_rate:.0%}" if r.win_rate is not None else "—")
    c3.metric(
        "Rule adherence",
        f"{r.rule_adherence_pct:.0%}" if r.rule_adherence_pct is not None else "—",
    )
    c4.metric(
        "VRP captured",
        f"{r.vrp_captured:+.1%}" if r.vrp_captured is not None else "—",
    )
    for o in r.overrides:
        st.error(f"override: {o}")
    if r.worst is not None:
        st.warning(f"Worst: {r.worst.symbol} {r.worst.pnl:+,.2f} — {r.worst.autopsy}")


def regime_tab() -> None:
    config = load_config()
    provider = _provider(config)
    vix = provider.get_quote("^VIX").price
    try:
        vix3m: float | None = provider.get_quote("^VIX3M").price
    except Exception:
        vix3m = None
    a = classify_regime(vix, vix3m)
    c1, c2, c3 = st.columns(3)
    c1.metric("VIX", f"{a.vix:.2f}")
    c2.metric("Regime", a.regime.value.upper())
    c3.metric("Sizing multiplier", f"{a.sizing_multiplier:.0%}")
    st.text(f"Term structure: {a.term_structure.value}")
    for n in a.notes:
        st.warning(n)
    try:
        hist = provider.get_price_history("^VIX", years=1)
        fig = go.Figure(go.Scatter(x=hist.dates, y=hist.closes, mode="lines"))
        for level in (20, 30, 40):
            fig.add_hline(y=level, line_dash="dot")
        fig.update_layout(title="VIX — 1 year", height=300)
        st.plotly_chart(fig, width="stretch")
    except Exception as exc:  # pragma: no cover - needs live data
        st.error(f"VIX history unavailable: {exc}")


def main() -> None:
    st.set_page_config(page_title="QuantDesk", page_icon="📉", layout="wide")
    st.title("QuantDesk")
    st.caption(
        "Decision support only — nothing here executes trades. "
        "POP, VRP, and backtest figures are estimates."
    )
    tab_names = ["Scanner", "Portfolio", "Journal", "Regime"]
    scanner, portfolio, journal, regime = st.tabs(tab_names)
    with scanner:
        try:
            scanner_tab()
        except Exception as exc:
            st.error(f"Scanner unavailable (data source down?): {exc}")
    with portfolio:
        try:
            portfolio_tab()
        except Exception as exc:
            st.error(f"Portfolio view failed: {exc}")
    with journal:
        try:
            journal_tab()
        except Exception as exc:
            st.error(f"Journal view failed: {exc}")
    with regime:
        try:
            regime_tab()
        except Exception as exc:
            st.error(f"Regime view unavailable (data source down?): {exc}")


if __name__ == "__main__" or st.runtime.exists():
    main()
