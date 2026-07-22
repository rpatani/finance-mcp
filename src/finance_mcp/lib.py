"""Embeddable finance client — standalone, no dependency on mcp_platform_core.

Free/keyless: CoinGecko (crypto) and Frankfurter (FX, ECB reference rates).
Premium: Alpha Vantage (equities), which needs an API key.

The MCP tool handlers wrap these calls in ``ctx.resilient.call(...)``; auth/tier/
cache/retry concerns live in the platform, so this stays a pure API client.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

COINGECKO_URL = "https://api.coingecko.com/api/v3"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1"
ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"


class FinanceLibError(Exception):
    """Base error for the finance client."""


class MissingApiKeyError(FinanceLibError):
    """Raised when an Alpha Vantage call is made without a key. Never retried."""


class UpstreamPayloadError(FinanceLibError):
    """Upstream returned HTTP 200 but not the expected data (e.g. rate-limit note)."""


class FinanceLib:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        alphavantage_api_key: str | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None
        self._av_key = alphavantage_api_key

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> FinanceLib:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # ---- CoinGecko (free, keyless) ------------------------------------------

    async def crypto_price(self, coin_id: str, vs_currency: str = "usd") -> dict[str, Any]:
        response = await self._client.get(
            f"{COINGECKO_URL}/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": vs_currency,
                "include_market_cap": "true",
                "include_24hr_change": "true",
            },
        )
        response.raise_for_status()
        data = response.json()
        entry = data.get(coin_id)
        if not entry:
            raise UpstreamPayloadError(f"no price data for coin {coin_id!r}")
        return {
            "coin_id": coin_id,
            "vs_currency": vs_currency,
            "price": entry.get(vs_currency),
            "market_cap": entry.get(f"{vs_currency}_market_cap"),
            "change_24h_pct": entry.get(f"{vs_currency}_24h_change"),
        }

    async def crypto_market(self, coin_ids: str, vs_currency: str = "usd") -> dict[str, Any]:
        response = await self._client.get(
            f"{COINGECKO_URL}/coins/markets",
            params={"vs_currency": vs_currency, "ids": coin_ids},
        )
        response.raise_for_status()
        rows = response.json()
        return {
            "vs_currency": vs_currency,
            "coins": [
                {
                    "id": row.get("id"),
                    "symbol": row.get("symbol"),
                    "price": row.get("current_price"),
                    "market_cap": row.get("market_cap"),
                    "rank": row.get("market_cap_rank"),
                    "change_24h_pct": row.get("price_change_percentage_24h"),
                }
                for row in rows
            ],
        }

    # ---- Frankfurter (free, keyless FX) -------------------------------------

    async def fx_rate(self, base: str, quote: str) -> dict[str, Any]:
        base_u, quote_u = base.upper(), quote.upper()
        response = await self._client.get(
            f"{FRANKFURTER_URL}/latest", params={"base": base_u, "symbols": quote_u}
        )
        response.raise_for_status()
        data = response.json()
        rate = (data.get("rates") or {}).get(quote_u)
        if rate is None:
            raise UpstreamPayloadError(f"no FX rate for {base_u}->{quote_u}")
        return {"base": base_u, "quote": quote_u, "rate": rate, "date": data.get("date")}

    # ---- Alpha Vantage (premium, needs key) ---------------------------------

    def _require_key(self) -> str:
        if not self._av_key:
            raise MissingApiKeyError("Alpha Vantage tools require ALPHAVANTAGE_API_KEY to be set")
        return self._av_key

    async def stock_quote(self, symbol: str) -> dict[str, Any]:
        key = self._require_key()
        response = await self._client.get(
            ALPHAVANTAGE_URL,
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": key},
        )
        response.raise_for_status()
        quote = response.json().get("Global Quote") or {}
        if not quote:
            raise UpstreamPayloadError(f"no quote for {symbol!r} (rate limited or unknown symbol)")
        return {
            "symbol": quote.get("01. symbol", symbol),
            "price": quote.get("05. price"),
            "change": quote.get("09. change"),
            "change_percent": quote.get("10. change percent"),
            "volume": quote.get("06. volume"),
            "latest_trading_day": quote.get("07. latest trading day"),
        }

    async def company_overview(self, symbol: str) -> dict[str, Any]:
        key = self._require_key()
        response = await self._client.get(
            ALPHAVANTAGE_URL,
            params={"function": "OVERVIEW", "symbol": symbol, "apikey": key},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("Symbol"):
            raise UpstreamPayloadError(
                f"no overview for {symbol!r} (rate limited or unknown symbol)"
            )
        return {
            "symbol": data.get("Symbol"),
            "name": data.get("Name"),
            "exchange": data.get("Exchange"),
            "sector": data.get("Sector"),
            "market_cap": data.get("MarketCapitalization"),
            "pe_ratio": data.get("PERatio"),
            "dividend_yield": data.get("DividendYield"),
            "description": data.get("Description"),
        }
