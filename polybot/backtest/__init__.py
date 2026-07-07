"""
polybot backtest engine.

A look-ahead-free replay of historical BTC data through the REAL Strategy and
RiskEngine (imported from the parent package), never a reimplementation.

Phases:
  data.py        (P1) historical klines + ground-truth 5m outcomes
  pricing.py     (P2) modeled Polymarket token prices + synthetic orderbook
  engine.py      (P3) chronological no-look-ahead replay -> backtest_trades.db
  report.py      (P4) terminal + HTML report with confidence intervals
  walkforward.py (P5) rolling train/test, out-of-sample only
  optimize.py    (P6) parameter sweep, walk-forward evaluated

Run modules from inside polybot/, e.g.  python -m backtest.data --days 180
"""
