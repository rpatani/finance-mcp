"""finance-mcp entrypoint: wire the five tools + core deps + transport.

Run with ``uv run finance-mcp``. Free crypto/FX tools need no secrets; the two
premium Alpha Vantage tools read ALPHAVANTAGE_API_KEY here (app-level), never in
core. Transport/keys/metrics are all driven by env via CoreConfig.
"""

from __future__ import annotations

import asyncio
import os

from mcp_platform_core import (
    CoreConfig,
    InMemoryRateLimiter,
    InMemoryResponseCache,
    LoggingUsageSink,
    MiddlewareDeps,
    ResilientCaller,
    ToolRegistry,
    build_mcp_server,
    build_metrics,
    create_logger,
    load_key_store,
    run_http,
    run_stdio,
)

from finance_mcp.lib import FinanceLib
from finance_mcp.tools.crypto import make_crypto_market_tool, make_crypto_price_tool
from finance_mcp.tools.fx import make_fx_rate_tool
from finance_mcp.tools.stocks import make_company_overview_tool, make_stock_quote_tool

SERVICE_NAME = "finance-mcp"
SERVICE_VERSION = "0.1.0"


def main() -> None:
    config = CoreConfig()
    log = create_logger(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        transport=config.transport,
        level=config.log_level,
    )
    metrics = build_metrics(config.metrics_backend, enabled=config.metrics_enabled)
    deps = MiddlewareDeps(
        key_store=load_key_store(config.keys_file),
        rate_limiter=InMemoryRateLimiter(),
        cache=InMemoryResponseCache(),
        usage_sink=LoggingUsageSink(log),
        metrics=metrics,
        logger=log,
        resilient=ResilientCaller(
            metrics=metrics,
            timeout_s=config.upstream_timeout_s,
            retries=config.upstream_retries,
            breaker_threshold=config.breaker_threshold,
            breaker_cooldown_s=config.breaker_cooldown_s,
        ),
    )

    # ALPHAVANTAGE_API_KEY is an app-level secret, read here — never in core.
    lib = FinanceLib(alphavantage_api_key=os.environ.get("ALPHAVANTAGE_API_KEY"))

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

    server = build_mcp_server(
        name=SERVICE_NAME, version=SERVICE_VERSION, registry=registry, deps=deps
    )

    async def _serve() -> None:
        try:
            if config.transport == "stdio":
                await run_stdio(server, api_key=config.api_key, log=log)
            else:
                await run_http(
                    server,
                    port=config.http_port,
                    mcp_path=config.http_path,
                    metrics=metrics,
                    metrics_port=config.metrics_port,
                    log=log,
                )
        finally:
            await lib.aclose()

    asyncio.run(_serve())


if __name__ == "__main__":
    main()
