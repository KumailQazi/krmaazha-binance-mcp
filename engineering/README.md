# Krmaazha Binance MCP — Engineering Knowledge Base

Welcome to the **Engineering Documentation Hub** for the `krmaazha-binance-mcp` project. This directory consolidates architectural specifications, technology stack justifications, data pipeline analytics, API catalogs, and agent skill inventories.

---

## 📚 Engineering Documentation Index

### 1. [Tech Stack & Architecture (`tech_stack_and_architecture.md`)](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/engineering/tech_stack_and_architecture.md)
* **Zero-Trust Intelligence Paradigm**: Dual-process isolation (`krmaazha-binance-mcp` server vs `krmaazha-binance-mcp-confirmer` gate).
* **Architecture Flowchart**: End-to-end Mermaid diagram illustrating the untrusted LLM client, read-only MCP server, local IPC socket, and physical confirmation dialog.
* **Technology Identification Table**: Detailed matrix of runtime (Python 3.12+, `uv`), MCP protocol (FastMCP 2.0.0), data pipelines (Binance REST, Vision archives, RSS), and typing/testing suites (`mypy strict`, `pytest-cov >= 90%`).
* **Engineering Reasoning**: Deep technical justification for zero-float accounting (`PlainDecimal`), zero-lookahead closed-bar slicing (`[:-1]`), survivorship-bias-free futures data pipelines (986 pairs, 306 delisted), and process-level key segregation.
* **Sub-Agent Directory**: Role specifications and governing boundaries for the 5 sub-agents under the Master Orchestrator.

---

### 2. [Dashboard Data Processing & API Specs (`dashboard_data_processing_and_apis.md`)](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/engineering/dashboard_data_processing_and_apis.md)
* **Continuous Polling & Bandwidth Metrics**:
  * **Tickers Ribbon** (`/api/tickers`): Polls every 5s (~3.2 KB ingress / ~700 B egress).
  * **Candles & Indicators** (`/api/klines`, `/api/indicators`): Polls every 15s (~6.0 KB ingress / ~7.7 KB egress).
  * **Signal Scanner** (`/api/signals-scan`): Polls 8 symbols every 30s (~72 KB ingress / ~5.8 KB egress).
  * **Macro Structure** (`/api/market-structure`): Polls every 60s (300s TTL cache, ~8 KB ingress per 5 min / ~850 B egress).
  * **Cycle Analysis** (`/api/cycle`): Polls every 60s (~18 KB ingress / ~350 B egress).
* **Throughput Calculations**:
  * **Per Minute**: ~195 KB ingress / ~28 KB egress (Total: **~223 KB/min**).
  * **Per Hour**: ~11.7 MB ingress / ~1.7 MB egress (Total: **~13.4 MB/hr**).
  * **Per 24 Hours**: ~280.8 MB ingress / ~40.8 MB egress (Total: **~321.6 MB/day**).
  * **Binance Rate Limit Consumption**: Consumes **~136 weight/min** (**11.3%** of the 1,200 wt/min threshold).
* **Internal Tools & Services**: Integration trace of `fetch_klines`, `compute_indicators`, `generate_signal_tool`, `get_order_book_liquidity`, `get_market_structure`, and `MasterOrchestratorAgent`.
* **External APIs**: Full endpoint inventory for Binance Spot, Alternative.me, CoinGecko, Mempool.space, and RSS news feeds.
* **JSON Payloads & Schemas**: Production schemas and sample responses for Market Structure, Tickers, Candlestick Bars, Composite Quantitative Signals, Order-Book Liquidity Audits, and Orchestrator Deliberations.

---

### 3. [Data & AI Skills Inventory (`skills_and_data_pipelines.md`)](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/engineering/skills_and_data_pipelines.md)
* **Installed Skills Registry**: 18 specialized skills installed from `skills.sh` via `npx skills add` into [`.agents/skills/`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/.agents/skills).
  * **Data Engineering**: `data-quality-frameworks`, `dbt-transformation-patterns`, `airflow-dag-patterns`, `spark-optimization`, `sql-optimization-patterns`, `postgresql-table-design`, `backtesting-frameworks`, `risk-metrics-calculation`.
  * **AI Engineering**: `rag-implementation`, `llm-evaluation`, `eval-harness-first`, `prompt-engineering-patterns`, `hybrid-search-implementation`, `embedding-strategies`, `vector-index-tuning`, `dataset-curation`, `ml-pipeline-workflow`, `ai-debt-detector`.
* **Agent Skills Binding**: Direct alignment with sub-agent responsibilities in [`AGENTS.md`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/AGENTS.md).

---

### 4. [MCP Server Manifest Spec (`server.json`)](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/engineering/server.json)
* **Official Registry Descriptor**: Formal MCP server registry schema configuration, package identifier (`krmaazha-binance-mcp`), stdio transport, and required environment variable definitions.

