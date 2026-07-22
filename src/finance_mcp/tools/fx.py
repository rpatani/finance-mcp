"""FX tool via Frankfurter (keyless ECB reference rates): get_fx_rate.

Note: DESIGN.md names exchangerate.host, which now requires an API key. Frankfurter
is a genuinely keyless equivalent (ECB reference rates), keeping the free tier
secret-free. Swap the base URL in lib.py if you standardize on another provider.
"""

from __future__ import annotations

from typing import Any

from mcp_platform_core import ToolContext, ToolDefinition
from pydantic import BaseModel, Field

from finance_mcp.lib import FinanceLib

_60S_MS = 60 * 1000


class FxRateInput(BaseModel):
    base: str = Field(min_length=3, max_length=3, description="Base currency ISO code, e.g. 'USD'.")
    quote: str = Field(
        min_length=3, max_length=3, description="Quote currency ISO code, e.g. 'EUR'."
    )


def make_fx_rate_tool(lib: FinanceLib) -> ToolDefinition:
    async def handler(args: FxRateInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call("frankfurter", lambda: lib.fx_rate(args.base, args.quote))

    return ToolDefinition(
        name="get_fx_rate",
        description=(
            "Get the latest foreign-exchange rate between two ISO currency codes (e.g. USD->EUR) "
            "using ECB reference rates. Free and keyless."
        ),
        input_model=FxRateInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_60S_MS,
        handler=handler,
    )
