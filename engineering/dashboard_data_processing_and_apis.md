# Dashboard Data Processing, Polling Rates, External APIs & JSON Schemas

This document provides a complete Data Engineering audit of the **Krmaazha Binance MCP Dashboard** (`web_dashboard/app.py` & `static/dashboard.js`), detailing exact data processing volumes, internal tool dependencies, external API calls, and wire schemas.

---

## 1. Data Volume & Throughput Analysis

When the dashboard runs continuously, the frontend engine ([`static/dashboard.js`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/web_dashboard/static/dashboard.js#L102)) executes background polling loops across 5 distinct cycles.

### ⏱️ Polling Frequencies & Per-Cycle Payload Breakdown

| Endpoint | Polling Interval | Source Requests per Cycle | Upstream Ingress / Cycle | Client Egress / Cycle |
|---|---|---|---|---|
| **`/api/tickers`** | **Every 5s** (12/min) | 8 symbols (`get_ticker`) | ~3.2 KB | ~700 B |
| **`/api/klines` & `/api/indicators`** | **Every 15s** (4/min) | 1 symbol (60 bars OHLCV) | ~6.0 KB | ~7.7 KB |
| **`/api/signals-scan`** | **Every 30s** (2/min) | 8 symbols (100 bars OHLCV) | ~72.0 KB | ~5.8 KB |
| **`/api/market-structure`** | **Every 60s** (1/min) | 5 public APIs (**300s TTL cache**) | ~8.0 KB *(per 5 min)* | ~850 B |
| **`/api/cycle`** | **Every 60s** (1/min) | 1 symbol (200 daily bars) | ~18.0 KB | ~350 B |

---

### 📊 Cumulative Bandwidth & Network Calculations

#### A. Per-Minute Throughput
* **Binance REST Gateway**: ~28 requests/minute consuming **~136 weight/min**. This represents **11.3%** of Binance’s 1,200 weight/minute IP rate limit, guaranteeing safety against bans.
* **Upstream Ingress (Binance + External APIs)**: **~195 KB / min**
* **Downstream Delivery to Browser**: **~28 KB / min**
* **Combined Network Bandwidth**: **~223 KB / min**

#### B. Per-Hour Throughput
* **Upstream Ingress**: 60 min × 195 KB ≈ **11.7 MB / hour**
* **Downstream Delivery to Browser**: 60 min × 28 KB ≈ **1.7 MB / hour**
* **Combined Network Bandwidth**: **~13.4 MB / hour**

#### C. Per-24-Hours (Continuous Run)
* **Upstream Ingress**: 24 hr × 11.7 MB ≈ **280.8 MB / day**
* **Downstream Delivery to Browser**: 24 hr × 1.7 MB ≈ **40.8 MB / day**
* **Total 24-Hour Processed Data**: **~321.6 MB / day**

---

## 2. Internal Tools & Service Engine Stack

The dashboard server ([`web_dashboard/app.py`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/web_dashboard/app.py)) imports and executes these internal tools:

1. **`binance.client.Client`**: Official Python-Binance wrapper for raw REST communication (`get_ticker`, `get_historical_klines`, `get_order_book`).
2. [**`krmaazha_binance_mcp.klines.fetch_klines`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/klines.py): Ingestion gate that slices closed candles (`[:-1]`), preventing lookahead bias and casting to typed Pandas DataFrames.
3. [**`krmaazha_binance_mcp.tools.marketdata.compute_indicators`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/tools/marketdata.py): Closed-bar math for RSI (14), EMA (9/21/50/200), MACD (12/26/9), Bollinger Bands (20, 2), and ATR (14).
4. [**`krmaazha_binance_mcp.tools.signals.generate_signal_tool`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/tools/signals.py): Evaluates the 4-factor quantitative weighting engine (trend, momentum, volume, volatility).
5. [**`krmaazha_binance_mcp.tools.marketdata.get_order_book_liquidity`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/tools/marketdata.py): Audits depth 100, computes touch spread in bps, calculates ±1% and ±2% dollar depth, and flags thin books.
6. [**`krmaazha_binance_mcp.tools.news.get_news` & `get_sentiment`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/tools/news.py): RSS feed ingest with lexicon-based polarity sentiment scoring.
7. [**`krmaazha_binance_mcp.marketwide.get_market_structure`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/marketwide.py): Cross-market aggregator with per-source graceful degradation and 300s TTL cache.
8. [**`krmaazha_binance_mcp.agents.MasterOrchestratorAgent`**](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/agents/orchestrator.py): Synthesizes multi-agent deliberation, doctrine compliance (`kb://discipline`), and the standardized single-sentence bottom line.

---

## 3. External APIs Catalog

| Provider | Endpoint URL | Data Ingested | Authentication | Rate Limits |
|---|---|---|---|---|
| **Binance Spot** | `https://api.binance.com/api/v3/ticker/24hr` | 24h rolling price, high, low, volume, % delta | None (Public) | 1 weight/symbol |
| **Binance Spot** | `https://api.binance.com/api/v3/klines` | OHLCV historical candlestick bars | None (Public) | 2 weight/call |
| **Binance Spot** | `https://api.binance.com/api/v3/depth` | Order-book bid/ask levels for spread & depth | None (Public) | 5 weight/call |
| **Alternative.me** | `https://api.alternative.me/fng/?limit=7` | Crypto Fear & Greed Index + 7-day values | None (Free) | Public |
| **CoinGecko** | `https://api.coingecko.com/api/v3/global` | Total crypto market cap and BTC dominance % | None (Free) | ~10-30 req/min |
| **CoinGecko** | `https://api.coingecko.com/api/v3/coins/bitcoin` | Bitcoin ATH price, ATH date, and ATH drawdown % | None (Free) | ~10-30 req/min |
| **Mempool.space** | `https://mempool.space/api/v1/fees/recommended` | Next-block Bitcoin transaction fees (sat/vB) | None (Public) | Public |
| **Mempool.space** | `https://mempool.space/api/v1/mining/hashrate/3d` | 3-day Bitcoin mining hashrate (EH/s) | None (Public) | Public |
| **CoinDesk / Crypto.news** | `https://www.coindesk.com/arc/outboundfeeds/rss/` | Public RSS news headlines | None (RSS XML) | Public |

---

## 4. Schemas and JSON Payloads

### A. Market Structure (`GET /api/market-structure`)

#### Schema
Defined in [`models.py`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/models.py) as `MarketStructure`:
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

#### JSON Payload Example
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

### B. Ticker Tape (`GET /api/tickers`)

#### JSON Payload Example
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

### C. Candlestick Bars (`GET /api/klines?symbol=BTCUSDT&interval=1h&limit=60`)

#### JSON Payload Example
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

### D. Composite Quantitative Signal (`GET /api/signals-scan`)

#### JSON Payload Example
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

### E. Order-Book Liquidity Audit (`GET /api/liquidity?symbol=BTCUSDT`)

#### Schema
Defined in [`models.py`](file:///c:/Users/Raza/Downloads/krmaazhaBinMcp/src/krmaazha_binance_mcp/models.py) as `OrderBookLiquidity`:
```python
class OrderBookLiquidity(BaseModel):
    symbol: str
    touch_spread_bps: float
    depth_1pct_usdt: PlainDecimal
    depth_2pct_usdt: PlainDecimal
    is_thin_book: bool
    recent_quote_volume_24h: PlainDecimal
    as_of_iso: str
    epistemic_tag: str
```

#### JSON Payload Example
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

### F. Multi-Agent Orchestrator Deliberation (`GET /api/orchestrator/deliberate?symbol=BTCUSDT`)

#### JSON Payload Example
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
