"""Tests for the standalone FinanceLib (respx-mocked, no live network)."""

from __future__ import annotations

import httpx
import pytest
import respx

from finance_mcp.lib import (
    ALPHAVANTAGE_URL,
    COINGECKO_URL,
    FRANKFURTER_URL,
    FinanceLib,
    MissingApiKeyError,
    UpstreamPayloadError,
)


@respx.mock
async def test_crypto_price_shape() -> None:
    respx.get(f"{COINGECKO_URL}/simple/price").mock(
        return_value=httpx.Response(
            200,
            json={"bitcoin": {"usd": 65956, "usd_market_cap": 1.3e12, "usd_24h_change": -0.45}},
        )
    )

    async with FinanceLib() as lib:
        result = await lib.crypto_price("bitcoin")

    assert result["price"] == 65956
    assert result["market_cap"] == 1.3e12
    assert result["change_24h_pct"] == -0.45


@respx.mock
async def test_crypto_price_unknown_coin_raises() -> None:
    respx.get(f"{COINGECKO_URL}/simple/price").mock(return_value=httpx.Response(200, json={}))

    async with FinanceLib() as lib:
        with pytest.raises(UpstreamPayloadError):
            await lib.crypto_price("not-a-coin")


@respx.mock
async def test_crypto_market_maps_rows() -> None:
    respx.get(f"{COINGECKO_URL}/coins/markets").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "current_price": 65961,
                    "market_cap": 1_323_000_000_000,
                    "market_cap_rank": 1,
                    "price_change_percentage_24h": -0.44,
                }
            ],
        )
    )

    async with FinanceLib() as lib:
        result = await lib.crypto_market("bitcoin")

    assert result["coins"][0]["symbol"] == "btc"
    assert result["coins"][0]["rank"] == 1


@respx.mock
async def test_fx_rate_uppercases_and_extracts() -> None:
    route = respx.get(f"{FRANKFURTER_URL}/latest").mock(
        return_value=httpx.Response(
            200, json={"amount": 1.0, "base": "USD", "date": "2026-07-22", "rates": {"EUR": 0.8766}}
        )
    )

    async with FinanceLib() as lib:
        result = await lib.fx_rate("usd", "eur")

    assert route.calls.last.request.url.params["base"] == "USD"
    assert result == {"base": "USD", "quote": "EUR", "rate": 0.8766, "date": "2026-07-22"}


@respx.mock
async def test_fx_rate_missing_pair_raises() -> None:
    respx.get(f"{FRANKFURTER_URL}/latest").mock(
        return_value=httpx.Response(200, json={"base": "USD", "rates": {}})
    )

    async with FinanceLib() as lib:
        with pytest.raises(UpstreamPayloadError):
            await lib.fx_rate("USD", "XYZ")


async def test_stock_quote_without_key_raises() -> None:
    async with FinanceLib() as lib:
        with pytest.raises(MissingApiKeyError):
            await lib.stock_quote("IBM")


@respx.mock
async def test_stock_quote_with_key_sends_apikey_and_maps() -> None:
    route = respx.get(ALPHAVANTAGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "Global Quote": {
                    "01. symbol": "IBM",
                    "05. price": "195.50",
                    "09. change": "1.20",
                    "10. change percent": "0.62%",
                    "06. volume": "3000000",
                    "07. latest trading day": "2026-07-22",
                }
            },
        )
    )

    async with FinanceLib(alphavantage_api_key="secret") as lib:
        result = await lib.stock_quote("IBM")

    assert route.calls.last.request.url.params["apikey"] == "secret"
    assert result["price"] == "195.50"
    assert result["change_percent"] == "0.62%"


@respx.mock
async def test_stock_quote_rate_limited_note_raises() -> None:
    # Alpha Vantage returns HTTP 200 with a note (no "Global Quote") when throttled.
    respx.get(ALPHAVANTAGE_URL).mock(
        return_value=httpx.Response(200, json={"Note": "rate limited"})
    )

    async with FinanceLib(alphavantage_api_key="secret") as lib:
        with pytest.raises(UpstreamPayloadError):
            await lib.stock_quote("IBM")


@respx.mock
async def test_company_overview_maps() -> None:
    respx.get(ALPHAVANTAGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "Symbol": "IBM",
                "Name": "International Business Machines",
                "Exchange": "NYSE",
                "Sector": "TECHNOLOGY",
                "MarketCapitalization": "180000000000",
                "PERatio": "20.5",
                "DividendYield": "0.045",
                "Description": "IBM is ...",
            },
        )
    )

    async with FinanceLib(alphavantage_api_key="secret") as lib:
        result = await lib.company_overview("IBM")

    assert result["name"] == "International Business Machines"
    assert result["pe_ratio"] == "20.5"


@respx.mock
async def test_http_error_propagates() -> None:
    respx.get(f"{COINGECKO_URL}/simple/price").mock(return_value=httpx.Response(500))

    async with FinanceLib() as lib:
        with pytest.raises(httpx.HTTPStatusError):
            await lib.crypto_price("bitcoin")
