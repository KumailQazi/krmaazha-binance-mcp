# Data & AI Engineering: Skills Inventory, Data Pipelines & API Specs

This document registers the newly installed Data & AI Engineering skills, analyzes the live dashboard data processing volumes, catalogs external APIs, and specifies JSON schemas.

---

## 1. Installed Skills Inventory (`skills.sh`)

Installed into [`.agents/skills/`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills) via `npx skills add` and mapped into [`AGENTS.md`](file:///c:/Users/Raza/Downloads/konnextBinMcp/AGENTS.md):

| Category | Skill Name | Source Path | Governing Purpose |
|---|---|---|---|
| **Data Eng** | `data-quality-frameworks` | [`.agents/skills/data-quality-frameworks`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/data-quality-frameworks/SKILL.md) | Data validation, Great Expectations, dbt tests, schema contracts. |
| **Data Eng** | `dbt-transformation-patterns` | [`.agents/skills/dbt-transformation-patterns`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/dbt-transformation-patterns/SKILL.md) | Analytics engineering, incremental data modeling, modular DAGs. |
| **Data Eng** | `airflow-dag-patterns` | [`.agents/skills/airflow-dag-patterns`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/airflow-dag-patterns/SKILL.md) | Production DAG design, sensor patterns, pipeline orchestration. |
| **Data Eng** | `spark-optimization` | [`.agents/skills/spark-optimization`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/spark-optimization/SKILL.md) | PySpark partition tuning, shuffle minimization, memory caching. |
| **Data Eng** | `sql-optimization-patterns` | [`.agents/skills/sql-optimization-patterns`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/sql-optimization-patterns/SKILL.md) | EXPLAIN query plans, composite indexes, CTE optimization. |
| **Data Eng** | `postgresql-table-design` | [`.agents/skills/postgresql-table-design`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/postgresql-table-design/SKILL.md) | Declarative partitioning, constraint rules, high-throughput ingestion. |
| **Data Eng** | `backtesting-frameworks` | [`.agents/skills/backtesting-frameworks`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/backtesting-frameworks/SKILL.md) | Zero-lookahead historical bar replay, slippage & fee modeling. |
| **Data Eng** | `risk-metrics-calculation` | [`.agents/skills/risk-metrics-calculation`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/risk-metrics-calculation/SKILL.md) | Value-at-Risk (VaR), Sharpe, Sortino, max drawdown, Kelly sizing. |
| **AI Eng** | `rag-implementation` | [`.agents/skills/rag-implementation`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/rag-implementation/SKILL.md) | Retrieval-augmented generation, chunking, embeddings, reranking. |
| **AI Eng** | `llm-evaluation` | [`.agents/skills/llm-evaluation`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/llm-evaluation/SKILL.md) | Benchmark evaluation harnesses, scoring rubrics, regression suites. |
| **AI Eng** | `eval-harness-first` | [`.agents/skills/eval-harness-first`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/eval-harness-first/SKILL.md) | Test-driven development for AI agents with golden sets & graders. |
| **AI Eng** | `prompt-engineering-patterns`| [`.agents/skills/prompt-engineering-patterns`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/prompt-engineering-patterns/SKILL.md) | Chain-of-thought, structured JSON schema outputs, few-shot prompts. |
| **AI Eng** | `hybrid-search-implementation`| [`.agents/skills/hybrid-search-implementation`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/hybrid-search-implementation/SKILL.md)| Reciprocal Rank Fusion (RRF) combining dense vectors and BM25. |
| **AI Eng** | `embedding-strategies` | [`.agents/skills/embedding-strategies`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/embedding-strategies/SKILL.md) | Vector embedding models, caching layers, dimensionality reduction. |
| **AI Eng** | `vector-index-tuning` | [`.agents/skills/vector-index-tuning`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/vector-index-tuning/SKILL.md) | HNSW and IVF-Flat indexing tradeoffs (recall vs latency). |
| **AI Eng** | `dataset-curation` | [`.agents/skills/dataset-curation`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/dataset-curation/SKILL.md) | Data deduplication, synthetic pair generation, fine-tuning prep. |
| **AI Eng** | `ml-pipeline-workflow` | [`.agents/skills/ml-pipeline-workflow`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/ml-pipeline-workflow/SKILL.md) | End-to-end MLOps from feature ingestion to model drift detection. |
| **AI Eng** | `ai-debt-detector` | [`.agents/skills/ai-debt-detector`](file:///c:/Users/Raza/Downloads/konnextBinMcp/.agents/skills/ai-debt-detector/SKILL.md) | Catches brittle agent logic, prompt drift, and silent failure modes. |

---

## 2. Dashboard Data Processing & Volume Analysis

When `web_dashboard/app.py` is actively running, its frontend client engine (`static/dashboard.js`) executes background polling loops.

### ⏱️ Polling Frequencies & Ingestion Rates

| Endpoint | Polling Interval | Upstream Calls (Source) | Data Ingress / Cycle | Egress to Client / Cycle |
|---|---|---|---|---|
| **`/api/tickers`** | **5 seconds** | 8 x Binance `get_ticker` | ~3.2 KB | ~700 B |
| **`/api/klines` + `/api/indicators`** | **15 seconds** | 1 x Binance `get_klines` (60 bars) | ~6.0 KB | ~7.7 KB |
| **`/api/signals-scan`** | **30 seconds** | 8 x Binance `get_klines` (100 bars) | ~72.0 KB | ~5.8 KB |
| **`/api/market-structure`** | **60 seconds** | 5 public APIs (Cached TTL 300s) | ~8.0 KB (per 5 min) | ~850 B |
| **`/api/cycle`** | **60 seconds** | 1 x Binance `get_klines` (200 bars) | ~18.0 KB | ~350 B |

### 📊 Aggregated Data Volume Estimates

* **Per Minute**:
  * Binance API Calls: ~28 requests (weight ~136 / 1200 allowed per min = **11.3% capacity**).
  * Data Ingested from External Sources: **~195 KB / min**.
  * Data Delivered to Web Client: **~28 KB / min**.
* **Per Hour**:
  * Ingress from Binance & Public APIs: **~11.7 MB / hour**.
  * Egress to Browser: **~1.7 MB / hour**.
  * Total Processed Network Bandwidth: **~13.4 MB / hour**.
* **Per 24 Hours (Continuous Run)**:
  * Upstream Ingress: **~280 MB / day**.
  * Browser Delivery: **~41 MB / day**.
  * Total 24-Hour Processed Data: **~321 MB / day**.

---

## 3. Tools & Internal Engine Stack

The dashboard uses the following internal Python tools and service modules:

1. **`binance.client.Client`**: Official wrapper communicating over HTTPS/TLS to Binance REST endpoints.
2. **`krmaazha_binance_mcp.klines.fetch_klines`**: Slices closed bars (`[:-1]`), validates timestamp continuity, and builds clean numeric Pandas DataFrames.
3. **`krmaazha_binance_mcp.tools.marketdata.compute_indicators`**: Zero-lookahead calculation of RSI (14), EMA (9, 21, 50, 200), MACD (12, 26, 9), Bollinger Bands (20, 2), and ATR (14).
4. **`krmaazha_binance_mcp.tools.signals.generate_signal_tool`**: Evaluates the 4-factor composite quantitative algorithm (trend, momentum, volume, volatility).
5. **`krmaazha_binance_mcp.tools.marketdata.get_order_book_liquidity`**: Audits order book depth within ±1% and ±2%, touch spread in bps, and flags thin book risk.
6. **`krmaazha_binance_mcp.tools.news.get_news` / `get_sentiment`**: RSS parser for CoinDesk and Crypto.news with lexical sentiment polarity scoring.
7. **`krmaazha_binance_mcp.marketwide.get_market_structure`**: Multi-source aggregator with per-source fault tolerance and 300s TTL in-memory caching.
8. **`krmaazha_binance_mcp.agents.MasterOrchestratorAgent`**: Coordinates multi-agent deliberation, doctrine compliance (`kb://discipline`), and single-sentence bottom line synthesis.

---

## 4. External APIs Catalog

| API Name | Endpoint URL | Purpose | Auth / Rate Limit |
|---|---|---|---|
| **Binance Spot Ticker** | `https://api.binance.com/api/v3/ticker/24hr?symbol={sym}` | 24h rolling high/low/volume/price | None / 1 wt per sym |
| **Binance Spot Klines** | `https://api.binance.com/api/v3/klines?symbol={sym}&interval={int}&limit={lim}` | OHLCV historical candlestick bars | None / 2 wt per call |
| **Binance Order Book** | `https://api.binance.com/api/v3/depth?symbol={sym}&limit=100` | Top 100 bids and asks for depth & spread | None / 5 wt per call |
| **Alternative.me** | `https://api.alternative.me/fng/?limit=7` | Crypto Fear & Greed Index & 7d history | Free / Public |
| **CoinGecko Global** | `https://api.coingecko.com/api/v3/global` | Total market cap and BTC dominance % | Free / ~10-30 req/min |
| **CoinGecko Bitcoin** | `https://api.coingecko.com/api/v3/coins/bitcoin` | BTC all-time high, ATH date, and ATH drawdown | Free / ~10-30 req/min |
| **Mempool.space Fees** | `https://mempool.space/api/v1/fees/recommended` | Next-block Bitcoin transaction fees (sat/vB) | Free / Public |
| **Mempool.space Hashrate** | `https://mempool.space/api/v1/mining/hashrate/3d` | 3-day Bitcoin network hashrate (EH/s) | Free / Public |
| **CoinDesk RSS** | `https://www.coindesk.com/arc/outboundfeeds/rss/` | Real-time crypto news headlines | RSS XML / Public |
| **Crypto.news RSS** | `https://crypto.news/feed/` | Real-time crypto market reporting | RSS XML / Public |

---

## 5. Data Schemas & Sample JSON Payloads

### A. Market Structure (`/api/market-structure`)

#### Pydantic Model Schema
```python
class MarketStructure(BaseModel):
    fear_greed: int | None
    fear_greed_label: str | None
    fear_greed_week: list[int]
    btc_dominance_pct: float | None
    total_market_cap_usd: float | None
    btc_ath_usd: PlainDecimal | None
    btc_ath_date: str | None
    btc_ath_change_pct: float | None
    mempool_fee_fast_sat_vb: int | None
    hashrate_avg_ehs: float | None
    notes: list[str]
    as_of: int
    disclaimer: str
```

#### JSON Payload
```json
{
  "fear_greed": 38,
  "fear_greed_label": "Fear",
  "fear_greed_week": [38, 42, 40, 44, 46, 50, 48],
  "btc_dominance_pct": 58.42,
  "total_market_cap_usd": 2420000000000.0,
  "btc_ath_usd": "108920.00",
  "btc_ath_date": "2025-01-20",
  "btc_ath_change_pct": -22.45,
  "mempool_fee_fast_sat_vb": 12,
  "hashrate_avg_ehs": 842.6,
  "notes": [],
  "as_of": 1740000000000,
  "disclaimer": "Market-wide context from free public sources..."
}
```

---

### B. Ticker Ribbon (`/api/tickers`)

#### JSON Payload
```json
[
  {
    "symbol": "BTCUSDT",
    "price": 84520.50,
    "change_24h": 1.84,
    "high_24h": 85100.00,
    "low_24h": 82950.00,
    "volume": 24512.45
  },
  {
    "symbol": "NOMUSDT",
    "price": 0.002452,
    "change_24h": -4.21,
    "high_24h": 0.002610,
    "low_24h": 0.002390,
    "volume": 12450890.0
  }
]
```

---

### C. Candlestick Bars (`/api/klines?symbol=BTCUSDT&interval=1h&limit=60`)

#### JSON Payload
```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "candles": [
    {
      "time": 1740000000000,
      "open": 84200.00,
      "high": 84650.00,
      "low": 84120.00,
      "close": 84520.50,
      "volume": 412.85
    }
  ]
}
```

---

### D. Composite Quantitative Signal (`/api/signals-scan`)

#### JSON Payload
```json
[
  {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "direction": "long",
    "score": 0.72,
    "price": "84520.50",
    "suggested_stop": "82450.00",
    "suggested_target": "88660.00",
    "atr_14": "1035.25",
    "breakdown": {
      "ema_trend": 0.30,
      "rsi_momentum": 0.22,
      "macd_cross": 0.20,
      "volume_confirmation": 0.00
    },
    "epistemic_tag": "[ESTIMATED]"
  }
]
```

---

### E. Order-Book Liquidity Audit (`/api/liquidity?symbol=BTCUSDT`)

#### JSON Payload
```json
{
  "symbol": "BTCUSDT",
  "touch_spread_bps": 0.12,
  "depth_1pct_usdt": "4850000.00",
  "depth_2pct_usdt": "11200000.00",
  "is_thin_book": false,
  "recent_quote_volume_24h": "2071780000.00",
  "as_of_iso": "2026-10-07T13:07:00Z",
  "epistemic_tag": "[VERIFIED]"
}
```

---

### F. Multi-Agent Orchestrator Deliberation (`/api/orchestrator/deliberate?symbol=BTCUSDT`)

#### JSON Payload
```json
{
  "status": "success",
  "symbol": "BTCUSDT",
  "timestamp_utc": "2026-10-07 13:07:00 UTC",
  "instrument": {
    "venue": "Binance Spot",
    "market_type": "SPOT",
    "quote": "USDT",
    "as_of_iso": "2026-10-07T13:07:00Z"
  },
  "deliberation": {
    "data_engineering": {
      "closed_bar_windowing": "PASS ([:-1] enforced)",
      "rate_limit_token_bucket": "HEALTHY (136 / 1200 wt/min)",
      "precision_policy": "ZERO_FLOAT (Decimal scale preserved)"
    },
    "security_key_guard": {
      "server_key_privilege": "READ_ONLY (Verified)",
      "confirmer_isolation": "PROCESS_ISOLATED (IPC local socket)",
      "execution_gate": "MANUAL_CLICK_REQUIRED"
    },
    "quantitative_risk": {
      "touch_spread_bps": 0.12,
      "net_rr_ratio": 2.14,
      "fee_friction_bps": 20.0,
      "mayer_multiple": 1.18,
      "epistemic_tag": "[ESTIMATED]"
    },
    "bottom_line": "At 2026-10-07 13:07:00 UTC, BTCUSDT on Binance Spot is trading at $84,520.50 in a confirmed accumulation structure. The setup is valid only if a 1h candle closes above $84,520.50; it is invalidated by a close below $82,450.00. Costs/risks include ~20 bps round-trip fees, 0.12 bps touch spread, and stop execution slippage. Otherwise, no trade."
  }
}
```
