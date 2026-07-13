"""Backtest report: plotly equity curves + metrics, saved as HTML.

The synthetic-pricing warning is embedded in the chart title itself so
it survives screenshots and copy-paste.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from quantdesk.backtest.engine import BacktestResult
from quantdesk.backtest.metrics import PerformanceSummary


def save_equity_report(
    result: BacktestResult,
    summaries: list[PerformanceSummary],
    benchmarks: dict[str, list[float]],
    out_dir: Path,
) -> Path:
    """Write an interactive HTML report; returns the file path.

    ``benchmarks`` maps label -> equity series aligned to result.dates.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=result.dates, y=result.equity, name=f"{result.mode} ({result.symbol})"
        )
    )
    for label, series in benchmarks.items():
        fig.add_trace(go.Scatter(x=result.dates, y=series, name=label))

    stats_lines = [
        f"{s.label}: CAGR {s.cagr:.1%} | vol {s.annualized_vol:.1%} | "
        f"Sharpe {s.sharpe:.2f} | Sortino {s.sortino:.2f} | "
        f"maxDD {s.max_drawdown:.1%} ({s.max_drawdown_days}d) | "
        f"ulcer {s.ulcer:.2f} | CVaR95 {s.cvar_95:.2%}"
        for s in summaries
    ]
    fig.update_layout(
        title=(
            f"{result.symbol} {result.mode} backtest — SYNTHETIC PRICING: "
            "directional/regime validity only<br><sub>"
            + "<br>".join(stats_lines)
            + "</sub>"
        ),
        xaxis_title="date",
        yaxis_title="equity ($)",
    )
    path = (
        out_dir
        / f"backtest_{result.symbol}_{result.mode}_{result.dates[-1].isoformat()}.html"
    )
    fig.write_html(str(path), include_plotlyjs="cdn")
    return path
