"""Universe management and per-symbol metric assembly for the screener.

The universe is the config watchlist (user-editable YAML). For each
symbol we assemble ``SymbolMetrics`` — spot, RV, ATM IV (solver-derived),
IV rank with honest sourcing, 50dma, earnings, and the best CSP strike
in the target delta band — then hand off to filters and the ranker.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

from quantdesk.analytics import black_scholes as bs
from quantdesk.analytics import volatility as vol
from quantdesk.analytics.chain import atm_iv_from_chain
from quantdesk.config import QuantDeskConfig
from quantdesk.data.cache import IVHistoryStore
from quantdesk.data.models import OptionChain
from quantdesk.data.provider import DataProvider
from quantdesk.screener.filters import csp_pipeline, run_filters
from quantdesk.screener.models import ScreenResult, StrikeCandidate, SymbolMetrics
from quantdesk.screener.ranker import score_results


def universe_symbols(config: QuantDeskConfig) -> list[str]:
    """The screening universe: de-duplicated config watchlist, order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for s in config.watchlist:
        u = s.strip().upper()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def account_usd(
    provider: DataProvider, config: QuantDeskConfig
) -> tuple[float, str]:
    """Account size in USD, converted from the account currency.

    Returns (usd, note). Uses a live FX quote (e.g. CADUSD=X) — never a
    hardcoded rate. If FX is unavailable, falls back to parity with a
    loud note rather than silently inventing a number.
    """
    size = config.account.size
    currency = config.account.currency.upper()
    if currency == "USD":
        return size, "account already in USD"
    try:
        fx = provider.get_quote(f"{currency}USD=X").price
        return size * fx, f"{currency}USD={fx:.4f} (live)"
    except Exception:
        return size, (
            f"WARNING: no {currency}USD quote — treating {currency} as USD 1:1; "
            "position caps are overstated"
        )


def usd_budget_per_position(
    provider: DataProvider, config: QuantDeskConfig
) -> tuple[float, str]:
    """Per-position collateral cap in USD (max_position_pct of the account)."""
    usd, note = account_usd(provider, config)
    return usd * config.risk.max_position_pct, note


def select_expiry(
    expirations: list[dt.date], dte_min: int, dte_max: int
) -> dt.date | None:
    """Expiry inside the DTE band, closest to its midpoint; None if none."""
    today = dt.date.today()
    in_band = [e for e in expirations if dte_min <= (e - today).days <= dte_max]
    if not in_band:
        return None
    target = (dte_min + dte_max) / 2
    return min(in_band, key=lambda e: abs((e - today).days - target))


def find_csp_strikes(
    chain: OptionChain,
    rate: float,
    div_yield: float,
    delta_min: float,
    delta_max: float,
) -> list[StrikeCandidate]:
    """OTM puts whose solver-derived delta falls in [delta_min, delta_max].

    IV is re-solved per strike from mid price (never trusted from the
    provider); unquotable or unsolvable contracts are skipped silently —
    they are unusable, not errors.
    """
    today = dt.date.today()
    dte = max((chain.expiry - today).days, 1)
    t_years = dte / 365.0
    out: list[StrikeCandidate] = []
    for contract in chain.puts:
        if contract.strike >= chain.spot:
            continue  # CSP writes OTM puts only
        mid = contract.mid
        if mid is None or mid <= 0:
            continue
        try:
            iv = bs.implied_vol(
                "put", mid, chain.spot, contract.strike, t_years, rate, div_yield
            )
        except ValueError:
            continue
        greeks = bs.bs_greeks(
            "put", chain.spot, contract.strike, t_years, rate, iv, div_yield
        )
        if not (delta_min <= greeks.delta <= delta_max):
            continue
        out.append(
            StrikeCandidate(
                contract=contract,
                iv=iv,
                delta=greeks.delta,
                mid=mid,
                spread_pct=contract.spread_pct,
                open_interest=contract.open_interest,
                volume=contract.volume,
                collateral=contract.strike * 100.0,
                annualized_yield=(mid / contract.strike) * (365.0 / dte),
            )
        )
    out.sort(key=lambda c: c.annualized_yield, reverse=True)
    return out


def compute_iv_rank(
    symbol: str,
    atm_iv: float,
    closes: list[float],
    store: IVHistoryStore,
    min_own_days: int,
) -> tuple[float, str, int]:
    """(rank, source, observations). Own IV history once mature enough,
    else bootstrap against the trailing rolling-RV20 distribution —
    labeled so nobody mistakes the bootstrap for the real thing."""
    own = [iv for _, iv in store.history(symbol)]
    if len(own) >= min_own_days:
        return vol.iv_rank(atm_iv, own), "own-iv-history", len(own)
    rv_series = vol.rolling_cc_vol_series(closes, 20)[-252:]
    if rv_series:
        return vol.iv_rank(atm_iv, rv_series), "rv-bootstrap", len(own)
    return 50.0, "no-history", len(own)


def build_symbol_metrics(
    provider: DataProvider,
    symbol: str,
    config: QuantDeskConfig,
    store: IVHistoryStore,
) -> SymbolMetrics:
    """Assemble all screening inputs for one symbol. Raises on unusable data."""
    rate = config.data.risk_free_rate
    csp = config.strategy.csp

    quote = provider.get_quote(symbol)
    history = provider.get_price_history(symbol, years=5)
    closes = history.closes
    if len(closes) < 60:
        raise RuntimeError(f"only {len(closes)} bars of history")
    div_yield = provider.get_dividend_yield(symbol)
    earnings = provider.get_next_earnings(symbol)

    rv_20d = vol.close_to_close_vol(closes, 20)
    dma_50 = sum(closes[-50:]) / 50.0

    expiry = select_expiry(
        provider.get_expirations(symbol), csp.dte_min, csp.dte_max
    )
    if expiry is None:
        raise RuntimeError(f"no expiry in {csp.dte_min}-{csp.dte_max} DTE band")
    chain = provider.get_option_chain(symbol, expiry)
    dte = (expiry - dt.date.today()).days

    atm_iv = atm_iv_from_chain(chain, rate, div_yield)
    if atm_iv is None:
        raise RuntimeError("ATM IV unsolvable from quotes")
    store.record(symbol, dt.date.today(), atm_iv)  # grow our IV history

    iv_rank, rank_source, obs = compute_iv_rank(
        symbol, atm_iv, closes, store, config.screener.own_iv_history_min_days
    )

    strikes = find_csp_strikes(
        chain, rate, div_yield, csp.delta_min, csp.delta_max
    )
    return SymbolMetrics(
        symbol=symbol,
        spot=quote.price,
        expiry=expiry,
        dte=dte,
        atm_iv=atm_iv,
        rv_20d=rv_20d,
        vrp=vol.vrp(atm_iv, rv_20d),
        iv_rank=iv_rank,
        iv_rank_source=rank_source,
        iv_history_days=obs,
        dma_50=dma_50,
        next_earnings=earnings,
        best_strike=strikes[0] if strikes else None,
    )


def scan_universe(
    provider: DataProvider,
    config: QuantDeskConfig,
    symbols: list[str] | None = None,
) -> tuple[list[ScreenResult], list[ScreenResult], str]:
    """Screen the universe for CSP candidates.

    Returns (ranked_passing, excluded, budget_note). Data failures never
    abort the scan — they become queryable exclusions.
    """
    store = IVHistoryStore(config.db_path)
    names = symbols if symbols is not None else universe_symbols(config)
    cap_usd, budget_note = usd_budget_per_position(provider, config)
    filters = csp_pipeline(config, cap_usd)

    results: list[ScreenResult] = []

    def screen_one(sym: str) -> ScreenResult:
        try:
            metrics = build_symbol_metrics(provider, sym, config, store)
        except Exception as exc:  # noqa: BLE001 — reason preserved for --explain
            return ScreenResult(symbol=sym, error=str(exc))
        return ScreenResult(
            symbol=sym, metrics=metrics, filters=run_filters(metrics, filters)
        )

    with ThreadPoolExecutor(max_workers=config.screener.max_workers) as pool:
        futures = {pool.submit(screen_one, s): s for s in names}
        for future in as_completed(futures):
            results.append(future.result())

    ranked = score_results(results, config)
    excluded = [r for r in results if not r.passed]
    return ranked, excluded, budget_note
