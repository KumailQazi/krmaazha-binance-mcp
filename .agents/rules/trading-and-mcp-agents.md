# Agent Roles & Behavioral Guidelines for Krmaazha Binance MCP

This repository implements a security-first Model Context Protocol (MCP) server for Binance Spot and an offline quantitative research engine. All agent interactions must conform to the specialized roles below.

---

## 1. Security & Key Guard Agent
* **Zero-Trust Credential Isolation**: The MCP server (`krmaazha-binance-mcp`) must ONLY hold `BINANCE_READ_*` keys. The trade key (`BINANCE_TRADE_*`) must strictly live in the separate `krmaazha-binance-mcp-confirmer` process.
* **No Auto-Execution**: Never create code or tool pathways that bypass the physical human confirmation gate.
* **API Permission Auditing**: The server must abort at startup on mainnet if its read key possesses spot trading, margin, futures, or withdrawal permissions.
* **Git Cleanliness**: Never commit credentials, secrets, or active API keys in `.mcp.json`, environment files, or repository tests.

---

## 2. Quantitative & Discipline Consultant Agent
* **Grounding in Doctrine**: Every investment or market output must align with `kb://discipline` (Rules 1–6 for spot accumulation, Rule 7 for systematic research) and `kb://research/no-edge`.
* **Zero-Lookahead Backtesting**: Historical signals must always be computed at candle close `t` and filled at open `t+1`. Never mark fills to the closing price of the signal candle.
* **Survivorship Bias Elimination**: Always test against full historical universes (including delisted pairs).
* **Behavioral Guidance**: Never output speculative price predictions or timing calls. Signals are statistical context, not financial advice.

---

## 3. MCP Protocol & Tool Design Agent
* **Strict Parameter Typing**: Use Python `Decimal` for all order prices, quantities, and notionals.
* **Canonical Wire Protocol**: IPC between the server and confirmer is restricted to `register` and `status` types transporting `CanonicalOrder`. No generic RPC execution method.
* **Clean Error Scrubbing**: Sanitize all exception messages before returning them to the model; never leak raw API keys, secrets, or internal nonces.

---

## 4. Financial Dashboard & UX Agent
* **High-Density Terminal Ergonomics**: Maintain a curated, modern palette (obsidian `#07090e`, Binance gold `#f0b90b`, emerald `#0ecb81`, crimson `#f6465d`, cyan `#00f0ff`).
* **Micro-Cap Price Precision**: Format sub-dollar tokens (e.g. `NOM`, `RESOLV`, `XVG`) with up to 6 decimal places (`$0.002452`) to prevent truncation errors.
* **Real-Time Data Freshness**: Provide clear "Last Fetched" timestamps and auto-polling loops (5s tickers, 15s candles, 30s signals).
