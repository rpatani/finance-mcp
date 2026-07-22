"""Equity tools via Alpha Vantage (premium, server-side key).

Exposes get_stock_quote and get_company_overview.
"""

from __future__ import annotations

from typing import Any

from mcp_platform_core import ToolContext, ToolDefinition
from pydantic import BaseModel, Field

from finance_mcp.lib import FinanceLib

_30S_MS = 30 * 1000
_6H_MS = 6 * 60 * 60 * 1000


class StockQuoteInput(BaseModel):
    symbol: str = Field(description="Equity ticker symbol, e.g. 'IBM' or 'AAPL'.")


class CompanyOverviewInput(BaseModel):
    symbol: str = Field(description="Equity ticker symbol, e.g. 'IBM' or 'AAPL'.")


def make_stock_quote_tool(lib: FinanceLib) -> ToolDefinition:
    async def handler(args: StockQuoteInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call("alphavantage", lambda: lib.stock_quote(args.symbol))

    return ToolDefinition(
        name="get_stock_quote",
        description=(
            "Get the latest price, change and volume for an equity ticker via Alpha Vantage. "
            "Premium tier; requires ALPHAVANTAGE_API_KEY."
        ),
        input_model=StockQuoteInput,
        min_tier="premium",
        cost_units=5,
        cache_ttl_ms=_30S_MS,
        handler=handler,
    )


def make_company_overview_tool(lib: FinanceLib) -> ToolDefinition:
    async def handler(args: CompanyOverviewInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call("alphavantage", lambda: lib.company_overview(args.symbol))

    return ToolDefinition(
        name="get_company_overview",
        description=(
            "Get company fundamentals (name, sector, market cap, P/E, dividend yield, description) "
            "for an equity ticker via Alpha Vantage. Premium tier; requires ALPHAVANTAGE_API_KEY."
        ),
        input_model=CompanyOverviewInput,
        min_tier="premium",
        cost_units=5,
        cache_ttl_ms=_6H_MS,
        handler=handler,
    )
