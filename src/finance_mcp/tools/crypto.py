"""Crypto tools via CoinGecko (keyless, free): get_crypto_price, get_crypto_market."""

from __future__ import annotations

from typing import Any

from mcp_platform_core import ToolContext, ToolDefinition
from pydantic import BaseModel, Field

from finance_mcp.lib import FinanceLib

_15S_MS = 15 * 1000
_30S_MS = 30 * 1000


class CryptoPriceInput(BaseModel):
    coin_id: str = Field(
        default="bitcoin", description="CoinGecko coin id, e.g. 'bitcoin', 'ethereum'."
    )
    vs_currency: str = Field(default="usd", description="Fiat/crypto to price against, e.g. 'usd'.")


class CryptoMarketInput(BaseModel):
    coin_ids: str = Field(
        default="bitcoin",
        description="Comma-separated CoinGecko coin ids, e.g. 'bitcoin,ethereum'.",
    )
    vs_currency: str = Field(default="usd", description="Fiat/crypto to price against, e.g. 'usd'.")


def make_crypto_price_tool(lib: FinanceLib) -> ToolDefinition:
    async def handler(args: CryptoPriceInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "coingecko", lambda: lib.crypto_price(args.coin_id, args.vs_currency)
        )

    return ToolDefinition(
        name="get_crypto_price",
        description=(
            "Get the current price, market cap and 24h change for a cryptocurrency by CoinGecko "
            "coin id. Free and keyless."
        ),
        input_model=CryptoPriceInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_15S_MS,
        handler=handler,
    )


def make_crypto_market_tool(lib: FinanceLib) -> ToolDefinition:
    async def handler(args: CryptoMarketInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "coingecko", lambda: lib.crypto_market(args.coin_ids, args.vs_currency)
        )

    return ToolDefinition(
        name="get_crypto_market",
        description=(
            "Get market data (price, market cap, rank, 24h change) for one or more "
            "cryptocurrencies by comma-separated CoinGecko coin ids. Free and keyless."
        ),
        input_model=CryptoMarketInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_30S_MS,
        handler=handler,
    )
