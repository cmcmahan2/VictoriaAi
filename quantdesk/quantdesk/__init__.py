"""QuantDesk — personal quant options analysis terminal.

Decision support only. This package never places orders and has no
brokerage integration. The core edge hypothesis is the volatility risk
premium (VRP): implied volatility has historically exceeded subsequently
realized volatility, so systematically selling richly priced options —
with strict sizing, diversification, and event-risk rules — has produced
superior risk-adjusted returns (cf. Cboe PUT/BXM benchmark indices).
Every module traces back to measuring, harvesting, or risk-managing
that premium.
"""

__version__ = "0.1.0"
