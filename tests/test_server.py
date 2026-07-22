"""Server wiring tests: tools listed with flat schemas, tier gating, free tool runs."""

from __future__ import annotations

import json

import httpx
import respx
import structlog
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_platform_core import (
    ApiKeyRecord,
    InMemoryKeyStore,
    InMemoryRateLimiter,
    InMemoryResponseCache,
    LoggingUsageSink,
    MiddlewareDeps,
    NullMetrics,
    ResilientCaller,
    ToolRegistry,
    build_mcp_server,
)
from mcp_platform_core.server import current_api_key

from finance_mcp.lib import COINGECKO_URL, FinanceLib
from finance_mcp.tools.crypto import make_crypto_market_tool, make_crypto_price_tool
from finance_mcp.tools.fx import make_fx_rate_tool
from finance_mcp.tools.stocks import make_company_overview_tool, make_stock_quote_tool

EXPECTED_TOOLS = {
    "get_crypto_price",
    "get_crypto_market",
    "get_fx_rate",
    "get_stock_quote",
    "get_company_overview",
}


def _build(lib: FinanceLib):
    keys = InMemoryKeyStore(
        {
            "premium-key": ApiKeyRecord(
                api_key="premium-key", owner="pro", tier="premium", rate_limit_per_minute=100
            )
        }
    )
    deps = MiddlewareDeps(
        key_store=keys,
        rate_limiter=InMemoryRateLimiter(),
        cache=InMemoryResponseCache(),
        usage_sink=LoggingUsageSink(structlog.get_logger()),
        metrics=NullMetrics(),
        logger=structlog.get_logger(),
        resilient=ResilientCaller(),
    )
    registry = ToolRegistry()
    registry.register_all(
        [
            make_crypto_price_tool(lib),
            make_crypto_market_tool(lib),
            make_fx_rate_tool(lib),
            make_stock_quote_tool(lib),
            make_company_overview_tool(lib),
        ]
    )
    return build_mcp_server(name="finance-mcp", version="0.1.0", registry=registry, deps=deps)


async def test_lists_all_five_tools_with_flat_schemas() -> None:
    server = _build(FinanceLib())
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()

    tools = {t.name: t for t in result.tools}
    assert set(tools) == EXPECTED_TOOLS
    assert set(tools["get_fx_rate"].inputSchema["properties"]) == {"base", "quote"}


@respx.mock
async def test_free_crypto_tool_runs() -> None:
    respx.get(f"{COINGECKO_URL}/simple/price").mock(
        return_value=httpx.Response(
            200, json={"bitcoin": {"usd": 65956, "usd_market_cap": 1.3e12, "usd_24h_change": -0.4}}
        )
    )
    server = _build(FinanceLib())
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_crypto_price", {"coin_id": "bitcoin"})

    assert result.isError is False
    assert json.loads(result.content[0].text)["price"] == 65956


async def test_premium_tool_rejected_for_anonymous() -> None:
    server = _build(FinanceLib(alphavantage_api_key="k"))
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_stock_quote", {"symbol": "IBM"})

    assert result.isError is True
    assert "tier" in result.content[0].text.lower()


@respx.mock
async def test_premium_tool_allowed_with_premium_key() -> None:
    respx.get("https://www.alphavantage.co/query").mock(
        return_value=httpx.Response(
            200, json={"Global Quote": {"01. symbol": "IBM", "05. price": "1"}}
        )
    )
    server = _build(FinanceLib(alphavantage_api_key="k"))
    token = current_api_key.set("premium-key")  # what the transport would set from the header
    try:
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool("get_stock_quote", {"symbol": "IBM"})
    finally:
        current_api_key.reset(token)

    assert result.isError is False
    assert json.loads(result.content[0].text)["symbol"] == "IBM"
