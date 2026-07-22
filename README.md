# finance-mcp

A finance / market-data **MCP server** built on
[`mcp-platform-core`](https://github.com/your-org/mcp-platform-py) — it consumes
the core as an external, version-pinned library and adds only the finance tools.
It demonstrates the **server-side API key** auth style: free tools are keyless,
premium tools use one server-held Alpha Vantage key gated behind the `premium`
tier.

## Tools

| Tool | Provider | Tier | Cache TTL | Cost |
|---|---|---|---|---|
| `get_crypto_price` | CoinGecko | free | 15 s | 1 |
| `get_crypto_market` | CoinGecko | free | 30 s | 1 |
| `get_fx_rate` | Frankfurter (ECB) | free | 60 s | 1 |
| `get_stock_quote` | Alpha Vantage | premium | 30 s | 5 |
| `get_company_overview` | Alpha Vantage | premium | 6 h | 5 |

The three free tools need **no secrets**. The two premium tools read
`ALPHAVANTAGE_API_KEY` and require the `premium` tier.

> FX note: DESIGN names exchangerate.host (now key-gated); this uses Frankfurter,
> a keyless ECB-rate equivalent, to keep the free tier secret-free.

## Core dependency

`mcp-platform-core` is pinned in `pyproject.toml` via a git tag. For local dev it
resolves from the local `mcp-platform-py` repo:

```toml
[tool.uv.sources]
mcp-platform-core = { git = "file:///Users/.../mcp-platform-py", tag = "mcp-platform-core-v0.1.0", subdirectory = "packages/core" }
```

When `mcp-platform-py` is pushed to GitHub, change the one `git = "file://…"`
line to `git = "https://github.com/<you>/mcp-platform-py"` — nothing else changes.

## Run locally (Mac)

```bash
uv sync

# stdio (keyless) — for Claude Desktop / CLI MCP clients
MCP_TRANSPORT=stdio uv run finance-mcp

# HTTP (keyless free tools; tiers via the keys file)
MCP_TRANSPORT=http MCP_HTTP_PORT=8080 MCP_KEYS_FILE=keys.example.json uv run finance-mcp

# smoke test a running HTTP server
./deploy/smoke-test.sh http://localhost:8080 http://localhost:9464
```

- MCP endpoint: `POST http://localhost:8080/mcp` · health: `/healthz`, `/readyz`
- Metrics: `http://localhost:9464/metrics`

Premium tools additionally need `ALPHAVANTAGE_API_KEY` **and** a `premium`-tier
key from the key store (send it as `Authorization: Bearer <key>`).

## Tests & gates

```bash
uv run pytest
uv run ruff check . && uv run mypy .
uv run pip-audit && uv run bandit -r src
```

## Docker

`docker compose -f deploy/docker-compose.yml up --build` — note the image build
pins core from git, so the local `file://` source must first be switched to a
reachable git remote (the container cannot see host paths). For local dev use
`uv run`.
