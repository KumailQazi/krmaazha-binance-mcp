# Privacy Policy: krmaazha-binance-mcp

**Last Updated:** October 2026  
**Publisher:** Kumail Qazi (@KumailQazi)  
**Project:** [krmaazha-binance-mcp](https://github.com/KumailQazi/krmaazha-binance-mcp)

---

## 1. Overview & Commitment to Zero-Knowledge

`krmaazha-binance-mcp` is a self-hosted, open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server designed for quantitative market intelligence and human-confirmed spot trading. 

**We do not collect, store, sell, or transmit any personal data, trade activity, or user credentials to external developer servers.** The software runs 100% locally on your machine or private infrastructure.

---

## 2. Data Handling & Secrets Architecture

### 2.1 API Keys and Secrets
- **Local Storage Only**: Your Binance API credentials (`BINANCE_READ_API_KEY`, `BINANCE_READ_API_SECRET`, and `BINANCE_TRADE_API_KEY`) reside exclusively in your local environment variables or client configuration.
- **Direct Exchange Communication**: All authenticated API requests travel strictly via encrypted TLS (HTTPS/WSS) directly from your local host to Binance's official servers (`api.binance.com` or `testnet.binance.vision`). No intermediary proxy, telemetry relay, or developer server ever sits in the network path.
- **Zero Secret Exfiltration**: The server employs strict output sanitization. API secrets, HMAC signatures, and internal nonces are scrubbed and never flow into tool outputs, LLM context windows, logs, or stack traces.

### 2.2 Key Isolation
- The MCP server process (`krmaazha-binance-mcp`) only accesses read-only credentials.
- The execution trade key lives strictly inside the separate, local confirmer process (`krmaazha-binance-mcp-confirmer`).
- Neither the LLM client nor any connected agent possesses direct execution authority or holds the trade secret.

---

## 3. Network Communication

The server communicates solely with the following network endpoints:
1. **Binance Official APIs**:
   - `api.binance.com` (Mainnet REST)
   - `testnet.binance.vision` (Testnet REST)
   - `data.binance.vision` (Public historical archives for offline research)
2. **Public Market Telemetry (Anonymous, Unauthenticated GET requests)**:
   - `api.alternative.me` (Fear & Greed Index)
   - `mempool.space` (Bitcoin on-chain fee estimates)
   - `api.coingecko.com` (Public global crypto market cap & dominance metrics)
   - Public RSS news feeds (CoinDesk, crypto.news)
3. **Local IPC**:
   - `127.0.0.1` / Local Unix domain sockets (Inter-process communication between MCP server and physical confirmer dialog).

---

## 4. Local Logging & Telemetry

- **No Remote Telemetry**: This software contains no analytics SDKs, tracking pixels, or remote error reporting.
- **Local Logs**: Audit logs (such as the trade confirmation history in `~/.config/krmaazha-binance-mcp/audit.log`) are stored locally on your machine and are never transmitted over the network.

---

## 5. Compliance with AI Directory Standards

This policy complies with privacy requirements established by:
- Anthropic Claude Desktop & Directory Guidelines
- OpenAI GPT & Agent Directory Guidelines
- Model Context Protocol (MCP) Registry Specifications

---

## 6. Open Source Verification

Because `krmaazha-binance-mcp` is licensed under the permissive [MIT License](LICENSE), the entire codebase is open for independent security and privacy auditing at:  
[https://github.com/KumailQazi/krmaazha-binance-mcp](https://github.com/KumailQazi/krmaazha-binance-mcp)
