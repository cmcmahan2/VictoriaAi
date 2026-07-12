"""QuantDesk CLI — analysis only, never execution.

Phase 1 commands:
    quantdesk quote AAPL      # vol snapshot: RV suite, ATM IV, VRP, expected move
    quantdesk config-show     # resolved configuration
    quantdesk regime          # VIX regime + sizing multiplier
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quantdesk import __version__
from quantdesk.analytics import black_scholes as bs
from quantdesk.analytics import volatility as vol
from quantdesk.analytics.regime import RegimeAssessment, classify_regime
from quantdesk.config import QuantDeskConfig, load_config
from quantdesk.data.cache import IVHistoryStore
from quantdesk.data.models import OptionChain, OptionType
from quantdesk.data.provider import DataProvider, YFinanceProvider

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


def _atm_iv_from_chain(
    chain: OptionChain, rate: float, div_yield: float
) -> float | None:
    """ATM IV: average of solver-derived call and put IV at the ATM strike.

    Uses QuantDesk's own Brent solver on mid prices — yfinance's IV field
    is untrustworthy. Returns None if neither side is solvable.
    """
    t_years = max((chain.expiry - dt.date.today()).days, 1) / 365.0
    strike = chain.atm_strike()
    ivs: list[float] = []
    opt_types: tuple[OptionType, ...] = ("call", "put")
    for opt_type in opt_types:
        contract = chain.contract_at(opt_type, strike)
        mid = contract.mid if contract else None
        if mid is None or mid <= 0:
            continue
        try:
            ivs.append(
                bs.implied_vol(opt_type, mid, chain.spot, strike, t_years, rate, div_yield)
            )
        except ValueError:
            continue
    return sum(ivs) / len(ivs) if ivs else None


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
    atm_iv = _atm_iv_from_chain(chain, rate, div_yield)

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
