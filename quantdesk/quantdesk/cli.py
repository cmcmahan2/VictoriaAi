"""QuantDesk CLI — analysis only, never execution.

Phase 1 commands:
    quantdesk quote AAPL      # vol snapshot: RV suite, ATM IV, VRP, expected move
    quantdesk config-show     # resolved configuration
    quantdesk regime          # VIX regime + sizing multiplier
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Optional

if TYPE_CHECKING:
    from quantdesk.strategies.base import TradeProposal

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quantdesk import __version__
from quantdesk.analytics import volatility as vol
from quantdesk.analytics.chain import atm_iv_from_chain
from quantdesk.analytics.regime import RegimeAssessment, classify_regime
from quantdesk.config import QuantDeskConfig, load_config
from quantdesk.data.cache import IVHistoryStore
from quantdesk.data.provider import DataProvider, YFinanceProvider
from quantdesk.screener.universe import build_symbol_metrics, scan_universe

app = typer.Typer(
    name="quantdesk",
    help="Personal quant options terminal. Research and decision support only — "
    "no order execution, ever.",
    no_args_is_help=True,
)
console = Console()


def _provider(config: QuantDeskConfig) -> DataProvider:
    return YFinanceProvider(
        db_path=config.db_path,
        quote_ttl=config.data.quote_cache_ttl_seconds,
        chain_ttl=config.data.chain_cache_ttl_seconds,
        history_ttl=config.data.history_cache_ttl_seconds,
    )


def _nearest_expiry(expirations: list[dt.date], target_dte: int = 30) -> dt.date:
    """Expiry closest to target DTE, preferring >= 7 DTE to avoid noise."""
    today = dt.date.today()
    usable = [e for e in expirations if (e - today).days >= 7]
    pool = usable or expirations
    if not pool:
        raise ValueError("no expirations available")
    return min(pool, key=lambda e: abs((e - today).days - target_dte))


@app.command()
def quote(
    symbol: str,
    config_path: Annotated[
        Optional[Path], typer.Option("--config", help="Path to config.yaml")
    ] = None,
) -> None:
    """Volatility snapshot: spot, RV suite, ATM IV, IV rank, VRP, expected move."""
    config = load_config(config_path)
    provider = _provider(config)
    symbol = symbol.upper()
    rate = config.data.risk_free_rate

    q = provider.get_quote(symbol)
    history = provider.get_price_history(symbol, years=5)
    div_yield = provider.get_dividend_yield(symbol)
    earnings = provider.get_next_earnings(symbol)

    rv = vol.realized_vol_suite(
        history.opens, history.highs, history.lows, history.closes
    )

    expiry = _nearest_expiry(provider.get_expirations(symbol), target_dte=30)
    chain = provider.get_option_chain(symbol, expiry)
    dte = (expiry - dt.date.today()).days
    atm_iv = atm_iv_from_chain(chain, rate, div_yield)

    table = Table(title=f"{symbol}  —  {q.price:,.2f}", show_header=False)
    table.add_column("metric", style="bold cyan")
    table.add_column("value")

    for label, key in (
        ("RV 20d (close-close)", "cc_20d"),
        ("RV 30d (close-close)", "cc_30d"),
        ("RV 60d (close-close)", "cc_60d"),
        ("RV 90d (close-close)", "cc_90d"),
        ("RV 20d (Parkinson)", "parkinson_20d"),
        ("RV 20d (Yang-Zhang)", "yang_zhang_20d"),
    ):
        if key in rv:
            table.add_row(label, f"{rv[key]:.1%}")

    if atm_iv is not None:
        table.add_row(f"ATM IV ({dte} DTE, {expiry})", f"{atm_iv:.1%}")

        # Persist today's observation to build our own IV history.
        store = IVHistoryStore(config.db_path)
        store.record(symbol, dt.date.today(), atm_iv)
        iv_hist = [iv for _, iv in store.history(symbol)]
        rank = vol.iv_rank(atm_iv, iv_hist)
        maturity = vol.iv_history_maturity(len(iv_hist))
        table.add_row("IV rank (own history)", f"{rank:.0f}  — {maturity}")

        if "cc_20d" in rv:
            vrp_val = vol.vrp(atm_iv, rv["cc_20d"])
            color = "green" if vrp_val > 0 else "red"
            table.add_row(
                "VRP (IV30 − RV20) (estimate)",
                f"[{color}]{vrp_val:+.1%}[/{color}]"
                + ("  (options rich)" if vrp_val > 0 else "  (options cheap)"),
            )

        em = vol.expected_move(q.price, atm_iv, dte)
        table.add_row(
            f"Expected move to {expiry} (estimate)",
            f"±{em:,.2f}  ({em / q.price:.1%})",
        )
        strike = chain.atm_strike()
        call = chain.contract_at("call", strike)
        put = chain.contract_at("put", strike)
        if call and put and call.mid and put.mid:
            straddle = vol.straddle_implied_move(call.mid, put.mid, q.price)
            table.add_row(
                "Straddle-implied move", f"±{straddle * q.price:,.2f}  ({straddle:.1%})"
            )
    else:
        table.add_row("ATM IV", "[red]unsolvable from quotes[/red]")

    table.add_row("Dividend yield", f"{div_yield:.2%}")
    table.add_row(
        "Next earnings", earnings.isoformat() if earnings else "[dim]unknown[/dim]"
    )
    console.print(table)


@app.command()
def scan(
    strategy: Annotated[
        str, typer.Option("--strategy", help="Only 'csp' in Phase 2")
    ] = "csp",
    explain: Annotated[
        Optional[str],
        typer.Option("--explain", help="Show every filter verdict for one symbol"),
    ] = None,
    top: Annotated[int, typer.Option("--top", help="Rows to display")] = 15,
    config_path: Annotated[
        Optional[Path], typer.Option("--config", help="Path to config.yaml")
    ] = None,
) -> None:
    """Screen the watchlist for rich, liquid, rule-clean CSP candidates."""
    config = load_config(config_path)
    if strategy != "csp":
        console.print(
            f"[red]Strategy '{strategy}' not available.[/red] Phase 2 screens "
            "cash-secured puts only; covered calls and spreads arrive in Phase 3."
        )
        raise typer.Exit(1)
    provider = _provider(config)

    if explain is not None:
        _explain_symbol(provider, config, explain.upper())
        return

    ranked, excluded, budget_note = scan_universe(provider, config)

    table = Table(
        title=f"CSP scan — {dt.date.today()}  (per-position cap: {budget_note})",
        box=box.SIMPLE,
    )
    table.add_column("symbol", style="bold")
    for col in ("strike", "Δ", "DTE", "credit", "yld/yr", "IVR", "VRP", "spr", "score"):
        table.add_column(col, justify="right")
    for r in ranked[:top]:
        m = r.metrics
        assert m is not None and m.best_strike is not None and r.score is not None
        b = m.best_strike
        rank_tag = "" if m.iv_rank_source == "own-iv-history" else "*"
        table.add_row(
            m.symbol, f"{b.contract.strike:g}",
            f"{b.delta:.2f}", str(m.dte), f"{b.mid:,.2f}",
            f"{b.annualized_yield:.1%}", f"{m.iv_rank:.0f}{rank_tag}",
            f"{m.vrp:+.1%}",
            f"{b.spread_pct:.1%}" if b.spread_pct is not None else "—",
            f"{r.score.total:+.2f}",
        )
    console.print(table)
    if any(
        r.metrics is not None and r.metrics.iv_rank_source != "own-iv-history"
        for r in ranked[:top]
    ):
        console.print(
            "[dim]* IV rank bootstrapped from realized-vol distribution — own "
            "IV history still immature.[/dim]"
        )
    if not ranked:
        console.print(
            "[yellow]No symbol passed every filter today.[/yellow] That is a "
            "valid answer — the system only wants rule-clean setups."
        )
    console.print(
        f"[dim]{len(excluded)} symbols excluded — "
        f"`quantdesk scan --explain SYMBOL` shows why.[/dim]"
    )


def _explain_symbol(
    provider: DataProvider, config: QuantDeskConfig, symbol: str
) -> None:
    """Full filter breakdown for one symbol — every exclusion is queryable."""
    from quantdesk.screener.filters import csp_pipeline, run_filters
    from quantdesk.screener.universe import usd_budget_per_position

    store = IVHistoryStore(config.db_path)
    try:
        metrics = build_symbol_metrics(provider, symbol, config, store)
    except Exception as exc:  # noqa: BLE001 — surfaced verbatim to the user
        console.print(
            Panel(f"[red]data-error:[/red] {exc}", title=f"{symbol} — EXCLUDED")
        )
        raise typer.Exit(1) from None

    cap_usd, budget_note = usd_budget_per_position(provider, config)
    results = run_filters(metrics, csp_pipeline(config, cap_usd))

    table = Table(title=f"{symbol} — filter breakdown ({budget_note})")
    table.add_column("filter")
    table.add_column("verdict")
    table.add_column("detail")
    for f in results:
        verdict = "[green]PASS[/green]" if f.passed else "[red]FAIL[/red]"
        table.add_row(f.name, verdict, f.detail)
    console.print(table)
    b = metrics.best_strike
    strike_line = (
        f"best strike {b.contract.strike:g} (Δ {b.delta:.2f}, "
        f"credit {b.mid:,.2f}, ann.yield {b.annualized_yield:.1%})"
        if b
        else "no strike in delta band"
    )
    console.print(
        f"[dim]spot {metrics.spot:,.2f} | ATM IV {metrics.atm_iv:.1%} | "
        f"RV20 {metrics.rv_20d:.1%} | VRP {metrics.vrp:+.1%} | "
        f"IV rank {metrics.iv_rank:.0f} ({metrics.iv_rank_source}) | "
        f"{strike_line}[/dim]"
    )


@app.command()
def propose(
    strategy: Annotated[str, typer.Argument(help="csp | covered-call | put-credit-spread")],
    symbol: Annotated[str, typer.Argument(help="Underlying ticker")],
    top: Annotated[int, typer.Option("--top", help="Proposals to show")] = 3,
    cost_basis: Annotated[
        Optional[float],
        typer.Option("--cost-basis", help="Your share cost basis (covered calls)"),
    ] = None,
    config_path: Annotated[
        Optional[Path], typer.Option("--config", help="Path to config.yaml")
    ] = None,
) -> None:
    """Structure ranked trade proposals with full risk numbers and exit plan."""
    from quantdesk.screener.universe import select_expiry
    from quantdesk.strategies.base import Strategy
    from quantdesk.strategies.covered_call import CoveredCall
    from quantdesk.strategies.credit_spreads import PutCreditSpread
    from quantdesk.strategies.csp import CashSecuredPut

    config = load_config(config_path)
    symbol = symbol.upper()

    strategies: dict[str, Strategy] = {
        "csp": CashSecuredPut(),
        "covered-call": CoveredCall(cost_basis=cost_basis),
        "cc": CoveredCall(cost_basis=cost_basis),
        "put-credit-spread": PutCreditSpread(),
        "pcs": PutCreditSpread(),
    }
    strat = strategies.get(strategy)
    if strat is None:
        console.print(f"[red]Unknown strategy '{strategy}'.[/red] "
                      "Available: csp, covered-call, put-credit-spread")
        raise typer.Exit(1)
    if strat.name == "put-credit-spread" and config.account.account_type == "tfsa":
        console.print(
            "[red]BLOCKED:[/red] credit spreads need a margin account. Your "
            "config says account_type=tfsa — registered accounts can't hold "
            "spread positions, and CRA treats high-frequency option writing "
            "in registered accounts unkindly. Switch config to 'margin' if "
            "that's actually what you trade."
        )
        raise typer.Exit(1)

    provider = _provider(config)
    div_yield = provider.get_dividend_yield(symbol)
    csp_cfg = config.strategy.csp
    expiry = select_expiry(
        provider.get_expirations(symbol), csp_cfg.dte_min, csp_cfg.dte_max
    )
    if expiry is None:
        console.print(
            f"[red]No expiry in the {csp_cfg.dte_min}-{csp_cfg.dte_max} DTE band "
            f"for {symbol}.[/red]"
        )
        raise typer.Exit(1)
    chain = provider.get_option_chain(symbol, expiry)

    proposals = strat.propose(chain, config, div_yield)
    if not proposals:
        console.print(
            f"[yellow]No {strat.name} setup qualifies on {symbol} {expiry} — "
            "no strike meets the delta band / credit requirements.[/yellow]"
        )
        raise typer.Exit(0)
    for i, p in enumerate(proposals[:top], start=1):
        _print_proposal_card(i, p)
    _print_sizing(provider, config, proposals[0])


def _print_sizing(
    provider: DataProvider, config: QuantDeskConfig, p: TradeProposal
) -> None:
    """Risk-engine sizing for the top proposal (Phase 4)."""
    from quantdesk.risk.sizing import recommend_size
    from quantdesk.screener.universe import account_usd

    try:
        vix = provider.get_quote("^VIX").price
    except Exception:
        console.print("[yellow]No VIX quote — sizing skipped.[/yellow]")
        return
    usd, fx_note = account_usd(provider, config)
    if p.collateral <= 0:  # e.g. covered call: shares already owned
        console.print(
            "[dim]Sizing: no new collateral required (covered by shares).[/dim]"
        )
        return
    stop_loss_usd = (
        p.exit_plan.stop_loss_buyback - p.net_credit
    ) * 100.0  # loss if the stop is hit
    rec = recommend_size(
        account_usd=usd,
        collateral_per_contract=p.collateral,
        pop=p.pop_model,
        win_per_contract=p.net_credit * 100.0,
        loss_per_contract=stop_loss_usd,
        vix=vix,
        config=config,
    )
    lines = [
        f"account ${usd:,.0f} USD ({fx_note})   VIX {vix:.1f} "
        f"(multiplier {rec.regime_multiplier:.0%})",
        f"Kelly {rec.kelly_raw:.1%} raw → {rec.kelly_applied:.1%} at "
        f"{config.risk.kelly_fraction:.0%}-Kelly → final {rec.final_fraction:.1%} "
        f"of account",
        f"[bold]Recommended size: {rec.contracts} contract(s)[/bold] "
        f"(${rec.collateral_total:,.0f} collateral)",
        *[f"[yellow]• {n}[/yellow]" for n in rec.notes],
    ]
    console.print(Panel("\n".join(lines), title="Sizing (top proposal)"))


def _print_proposal_card(rank: int, p: TradeProposal) -> None:
    legs = "\n".join(
        f"  {leg.action.upper():4s} 1x {leg.contract.contract_symbol} "
        f"@ ~{leg.price:.2f}"
        for leg in p.legs
    )
    lines = [
        f"[bold]{legs}[/bold]",
        "",
        f"net credit [bold]{p.net_credit:.2f}[/bold]   "
        f"max profit ${p.max_profit:,.0f}   max loss ${p.max_loss:,.0f}   "
        f"collateral ${p.collateral:,.0f}",
        f"breakeven {', '.join(f'{b:,.2f}' for b in p.breakevens)}   "
        f"POP {p.pop_delta:.0%} (delta) / {p.pop_model:.0%} (model — estimates)   "
        f"ann. yield {p.annualized_yield_on_collateral:.1%}",
        f"greeks: Δ {p.greeks.delta_shares:+.0f} sh   "
        f"Γ {p.greeks.gamma_shares:+.1f} sh/$   "
        f"θ {p.greeks.theta_usd_day:+.2f} $/day   "
        f"vega {p.greeks.vega_usd_pt:+.2f} $/pt",
        "",
        "[bold]Exit plan[/bold]",
        *[f"  • {r}" for r in p.exit_plan.rules],
        "",
        p.thesis,
    ]
    if p.requires_margin_account:
        lines.insert(0, "[red bold]MARGIN ACCOUNT REQUIRED[/red bold]")
    for w in p.warnings:
        lines.insert(0, f"[yellow]⚠ {w}[/yellow]")
    console.print(
        Panel(
            "\n".join(lines),
            title=f"#{rank}  {p.underlying} {p.strategy}  {p.expiry} ({p.dte} DTE)",
        )
    )


@app.command()
def regime(
    config_path: Annotated[
        Optional[Path], typer.Option("--config", help="Path to config.yaml")
    ] = None,
) -> None:
    """Current VIX regime, term structure, and position-sizing multiplier."""
    config = load_config(config_path)
    provider = _provider(config)
    vix = provider.get_quote("^VIX").price
    try:
        vix3m: float | None = provider.get_quote("^VIX3M").price
    except Exception:
        vix3m = None
    assessment = classify_regime(vix, vix3m)
    _print_regime(assessment)


def _print_regime(a: RegimeAssessment) -> None:
    color = {
        "low": "blue", "normal": "green", "elevated": "yellow",
        "high": "red", "extreme": "bold red",
    }[a.regime.value]
    lines = [
        f"VIX: {a.vix:.2f}" + (f"   VIX3M: {a.vix_3m:.2f}" if a.vix_3m else ""),
        f"Regime: [{color}]{a.regime.value.upper()}[/{color}]   "
        f"Term structure: {a.term_structure.value}",
        f"New-position sizing multiplier: {a.sizing_multiplier:.0%}",
        *[f"• {n}" for n in a.notes],
    ]
    console.print(Panel("\n".join(lines), title="Volatility Regime"))


@app.command("config-show")
def config_show(
    config_path: Annotated[
        Optional[Path], typer.Option("--config", help="Path to config.yaml")
    ] = None,
) -> None:
    """Print the resolved configuration."""
    config = load_config(config_path)
    console.print_json(config.model_dump_json(indent=2))
    if config.account.account_type == "tfsa":
        console.print(
            "[yellow]Note:[/yellow] account_type=tfsa — credit spreads hidden "
            "(registered-account strategy limits; CRA business-income caution "
            "for high-frequency writing)."
        )


@app.command()
def version() -> None:
    """Print QuantDesk version."""
    console.print(f"quantdesk {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
