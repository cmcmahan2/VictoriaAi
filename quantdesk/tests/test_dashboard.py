"""Dashboard smoke test: the module must import cleanly outside Streamlit.

Full rendering needs a browser session; what CI can and should catch is
import errors, signature drift against the core modules, and accidental
top-level execution (the module guard must keep main() from running on
plain import).
"""

from __future__ import annotations


def test_dashboard_imports_without_running() -> None:
    import quantdesk.dashboard as dash

    assert callable(dash.main)
    # Tab functions exist and are wired to the same core modules.
    for fn in (dash.scanner_tab, dash.portfolio_tab, dash.journal_tab, dash.regime_tab):
        assert callable(fn)
