"""
Financial Research Tools — ported from OpenAlice equity/analysis tools.

These tools provide stock market data, financial ratios, insider trading,
earnings calendars, and technical analysis capabilities for the
financial_researcher agent and finance council.

Each tool returns structured JSON. Real implementations should call
provider APIs (yfinance, fmp, etc.) — these stubs return placeholder
data for testing and can be wired to live data sources.
"""

from __future__ import annotations

import json
from typing import Any


def _stub(name: str, params: dict, extra: dict | None = None) -> str:
    result: dict[str, Any] = {"tool": name, "status": "stub", "params": params}
    if extra:
        result.update(extra)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Equity Tools
# ---------------------------------------------------------------------------

def equity_get_profile(symbol: str) -> str:
    """Get company profile and key valuation metrics for a stock."""
    return _stub("equity_get_profile", {"symbol": symbol}, {
        "data": {
            "symbol": symbol,
            "name": f"{symbol} Inc.",
            "sector": "Technology",
            "industry": "Software",
            "description": f"Company profile for {symbol}",
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "ev_ebitda": None,
            "dividend_yield": None,
        }
    })


def equity_get_financials(symbol: str, type: str = "income", period: str = "annual", limit: int = 5) -> str:
    """Get financial statements (income, balance sheet, cash flow) for a company."""
    return _stub("equity_get_financials", {"symbol": symbol, "type": type, "period": period, "limit": limit}, {
        "data": {
            "symbol": symbol,
            "statement_type": type,
            "period": period,
            "entries": [],
        }
    })


def equity_get_ratios(symbol: str, period: str = "annual", limit: int = 5, ttm: str = "include") -> str:
    """Get financial ratios (profitability, liquidity, leverage, valuation) for a company."""
    return _stub("equity_get_ratios", {"symbol": symbol, "period": period, "limit": limit, "ttm": ttm}, {
        "data": {
            "symbol": symbol,
            "ttm_mode": ttm,
            "ratios": {
                "roe": None,
                "roa": None,
                "gross_margin": None,
                "net_margin": None,
                "current_ratio": None,
                "quick_ratio": None,
                "debt_equity": None,
                "pe_ratio": None,
                "pb_ratio": None,
                "ps_ratio": None,
                "dividend_yield": None,
            }
        }
    })


def equity_get_earnings_calendar(symbol: str = "", start_date: str = "", end_date: str = "") -> str:
    """Get upcoming and recent earnings release dates."""
    return _stub("equity_get_earnings_calendar", {"symbol": symbol, "start_date": start_date, "end_date": end_date}, {
        "data": {"earnings": []}
    })


def equity_get_insider_trading(symbol: str, limit: int = 20) -> str:
    """Get insider trading activity (buys/sells by executives and directors)."""
    return _stub("equity_get_insider_trading", {"symbol": symbol, "limit": limit}, {
        "data": {"transactions": []}
    })


def equity_get_short_interest(symbol: str) -> str:
    """Get share statistics and short interest for a stock."""
    return _stub("equity_get_short_interest", {"symbol": symbol}, {
        "data": {
            "symbol": symbol,
            "shares_outstanding": None,
            "float": None,
            "shares_short": None,
            "short_percent_of_float": None,
            "days_to_cover": None,
        }
    })


def equity_get_estimates(symbol: str) -> str:
    """Get analyst price-target consensus for a stock."""
    return _stub("equity_get_estimates", {"symbol": symbol}, {
        "data": {
            "symbol": symbol,
            "target_high": None,
            "target_low": None,
            "target_consensus": None,
            "target_median": None,
            "analyst_count": None,
        }
    })


def equity_discover(type: str = "active", sort_by: str = "default") -> str:
    """Discover trending stocks (gainers, losers, active, screeners)."""
    return _stub("equity_discover", {"type": type, "sort_by": sort_by}, {
        "data": {"type": type, "rows": []}
    })


# ---------------------------------------------------------------------------
# Analysis / Technical Indicators
# ---------------------------------------------------------------------------

def calculate_indicator(asset: str, formula: str, precision: int = 4) -> str:
    """Calculate technical indicators (SMA, RSI, MACD, etc.) for a ticker."""
    return _stub("calculate_indicator", {"asset": asset, "formula": formula, "precision": precision}, {
        "data": {"value": None, "formula": formula, "asset_class": asset}
    })


# ---------------------------------------------------------------------------
# Market Search
# ---------------------------------------------------------------------------

def market_search(query: str) -> str:
    """Search for a stock, ETF, or index by name or ticker symbol."""
    return _stub("market_search", {"query": query}, {
        "data": {"query": query, "results": []}
    })


# ---------------------------------------------------------------------------
# Financial Tool Definitions (for registry)
# ---------------------------------------------------------------------------

FINANCE_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "equity_get_profile",
        "description": "Get company profile and key valuation metrics for a stock. Returns company overview (name, sector, industry) combined with key metrics (market cap, PE ratio, PB ratio, EV/EBITDA, dividend yield).",
        "func": equity_get_profile,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. 'AAPL', 'MSFT'"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "equity_get_financials",
        "description": "Get financial statements for a company (income statement, balance sheet, or cash flow). Each entry is one fiscal period.",
        "func": equity_get_financials,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "type": {"type": "string", "enum": ["income", "balance", "cash"], "description": "Statement type"},
                "period": {"type": "string", "enum": ["annual", "quarter"], "description": "Fiscal period"},
                "limit": {"type": "integer", "description": "Number of periods (default 5)"},
            },
            "required": ["symbol", "type"],
        },
    },
    {
        "name": "equity_get_ratios",
        "description": "Get financial ratios: profitability (ROE, ROA, margins), liquidity (current, quick), leverage (debt/equity), valuation (P/E, P/B, P/S, dividend yield).",
        "func": equity_get_ratios,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "period": {"type": "string", "enum": ["annual", "quarter"]},
                "limit": {"type": "integer", "description": "Historical periods (default 5)"},
                "ttm": {"type": "string", "enum": ["include", "exclude", "only"], "description": "TTM handling"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "equity_get_earnings_calendar",
        "description": "Get upcoming and recent earnings release dates. Check before holding positions — earnings events carry significant risk.",
        "func": equity_get_earnings_calendar,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker (omit for market-wide)"},
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "equity_get_insider_trading",
        "description": "Get insider trading activity. Insider buying is often bullish; large insider selling may warrant caution.",
        "func": equity_get_insider_trading,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "limit": {"type": "integer", "description": "Transactions to return (default 20)"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "equity_get_short_interest",
        "description": "Get share statistics and short interest. Rising short interest with high days-to-cover = crowded short.",
        "func": equity_get_short_interest,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "equity_get_estimates",
        "description": "Get analyst price-target consensus. Compare consensus to current price for implied upside.",
        "func": equity_get_estimates,
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "equity_discover",
        "description": "Discover trending stocks: gainers, losers, most active, or screener lenses (undervalued_growth, growth_tech, aggressive_small_caps, undervalued_large_caps).",
        "func": equity_discover,
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["gainers", "losers", "active", "undervalued_growth", "growth_tech", "aggressive_small_caps", "undervalued_large_caps"]},
                "sort_by": {"type": "string", "enum": ["default", "relative_volume", "dollar_volume"]},
            },
            "required": ["type"],
        },
    },
    {
        "name": "calculate_indicator",
        "description": "Calculate technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, RVOL, OBV, MFI, VWAP) for equity, crypto, currency, or commodity.",
        "func": calculate_indicator,
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {"type": "string", "enum": ["equity", "crypto", "currency", "commodity"], "description": "Asset class"},
                "formula": {"type": "string", "description": "Formula, e.g. SMA(CLOSE('AAPL', '1d'), 50)"},
                "precision": {"type": "integer", "description": "Decimal places (default 4)"},
            },
            "required": ["asset", "formula"],
        },
    },
    {
        "name": "market_search",
        "description": "Search for a stock, ETF, or index by name or ticker symbol.",
        "func": market_search,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (name or ticker)"},
            },
            "required": ["query"],
        },
    },
]
