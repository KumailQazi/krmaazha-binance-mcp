# Krmaazha Binance MCP: Senior Data Engineering Architecture & Data Flow Review

**Author**: Senior Principal Data Systems Architect & Quantitative Engineer (10+ Years Experience)  
**System**: Krmaazha Binance MCP & Terminal V2  
**Target Architecture**: Defense-in-Depth Model Context Protocol (MCP) + Quantitative Algorithmic Engine + Real-Time Execution Dashboard

---

## 1. Executive System Evaluation

The **Krmaazha Binance MCP** architecture represents an institutional-grade, multi-tiered data processing and decisioning pipeline. Unlike conventional trading bots or naive LLM wrappers, this system is architected around four non-negotiable quantitative engineering tenets:
1. **Absolute Zero-Trust Credential Segregation**: Physical separation between read-only intelligence telemetry (`BINANCE_READ_*`) and state-mutating execution authority (`BINANCE_TRADE_*`).
2. **Mathematical & Epistemic Determinism**: Elimination of lookahead bias via closed-bar indexing ($t$), survivorship bias elimination across 986+ futures pairs, exact Python `Decimal` typing across financial boundaries, and trigger-anchored Net Risk/Reward accounting.
3. **Hierarchical Agent Governance**: Multi-agent orchestration triage where the `MasterOrchestratorAgent` coordinates specialized autonomous sub-agents (`DataEngineering`, `Security`, `Protocol`, `Quantitative`, `UX`) before synthesizing standardized institutional decisions.
4. **Real-Time Progressive Disclosure**: An ergonomics layer delivering high-density telemetry, micro-cap precision ($0.000001), interactive loss modeling, and progressive drill-downs.

---

## 2. End-to-End Data Flow Diagram (DFD)

```mermaid
flowchart TD
    subgraph S1["1. INGESTION & DATA SOURCING"]
        direction TB
        B_REST["Binance Public REST API<br/>• /api/v3/klines (15m, 1h, 4h, 1d)<br/>• /api/v3/depth (Order Book L2)<br/>• /api/v3/ticker/24hr (Tickers)"]
        F_HIST["Binance USD-M Futures Archive<br/>• 986 USD-M Instrument History<br/>• Delisted Token Audit Database"]
        RSS_EXT["External News Feeds (RSS)<br/>• CoinDesk, Decrypt, The Block<br/>• Bitcoin Magazine Lexicon"]
        MACRO_EXT["Macro Providers<br/>• Alternative.me (Fear & Greed)<br/>• Blockchain.info / Mempool (Hashrate)"]
    end

    subgraph S2["2. NORMALIZATION & INTEGRITY ENFORCEMENT"]
        direction TB
        VAL_SCHEMA["FastMCP & Pydantic Data Contracts<br/>• Strict Decimal Typing (No Float Drift)<br/>• ISO 8601 UTC Temporal Normalization<br/>• Missing Metric Safeguards (Null ATR/SMA)"]
        BIAS_GUARD["Quantitative Integrity Gates<br/>• Closed-Bar Windowing (Bar t close, exec t+1)<br/>• Survivorship Bias Elimination Filter<br/>• Unvalidated Sentiment Tagging ([UNVALIDATED])"]
    end

    subgraph S3["3. ANALYTIC COMPUTATION & SIGNAL ENGINE"]
        direction TB
        IND_ENGINE["Technical Indicator Engine<br/>• EMA 12/26 (Trend, 30%)<br/>• RSI 14 (Momentum, 20%)<br/>• MACD 12/26/9 Hist (Velocity, 20%)<br/>• Bollinger %B 20,2 (Compression, 15%)<br/>• Lexicon Sentiment (15%)"]
        LIQ_ENGINE["Liquidity & Depth Engine<br/>• Touch Spread (bps) Calculation<br/>• ±1% and ±2% Bid/Ask Depth (USDT)<br/>• Thin Book Fragility Classifier"]
        RR_ENGINE["Trigger-Anchored Risk Engine<br/>• Entry Trigger (T) Anchoring<br/>• Gross R:R = |Target-T| / |T-Stop|<br/>• Friction = 20 bps fee + spread + 5 bps slip<br/>• Net R:R = (Gross Rew - Fric) / (Gross Risk + Fric)"]
        DCA_ENGINE["Historical DCA Simulator<br/>• Multi-Month Cadence Backtest<br/>• 0.1% Modeled Taker Friction<br/>• DCA vs Lump-Sum Yield Differential"]
    end

    subgraph S4["4. MULTI-AGENT GOVERNANCE & ORCHESTRATION"]
        direction TB
        ORCH["🧠 Master Orchestrator Agent<br/>(Apex Triage & Institutional Synthesis)"]
        
        DATA_A["🏗️ Data Engineering Agent<br/>• Ingestion Health Audit<br/>• Pipeline Freshness Guard"]
        SEC_A["🛡️ Security Guard Agent<br/>• Key Isolation Check<br/>• Zero-Trust Verifier"]
        PROTO_A["⚡ Protocol Agent<br/>• CanonicalOrder Schema<br/>• Error Nonce Scrubbing"]
        QUANT_A["📊 Quantitative Agent<br/>• Telemetry Audit Gate<br/>• Trade Authorization Gate"]
        UX_A["🖥️ UX Agent<br/>• Epistemic Tagging<br/>• Micro-Cap Formatter"]
    end

    subgraph S5["5. SERVING & SECURE EXECUTION GATEWAY"]
        direction TB
        API_SRV["Fast Starlette REST Server<br/>(Uvicorn Async Runtime, Port 8999)<br/>• /api/tickers • /api/klines<br/>• /api/signals-scan • /api/orchestrator"]
        MCP_PIPE["FastMCP Stdio Server<br/>(Read-Only Tools for LLM/Claude)"]
        IPC_GATE["Physical Confirmer IPC Socket<br/>(Unix Domain Socket / Named Pipe)<br/>Strictly Isolated Process (BINANCE_TRADE_*)"]
    end

    subgraph S6["6. CLIENT DASHBOARD & TERMINAL V2"]
        direction TB
        D_HERO["Above-the-Fold Decision Terminal<br/>• Canonical State (WAITING / READY / AVOID)<br/>• Execution Bounds (Trigger, Stop, Target)<br/>• Trigger-Anchored Net R:R & Formula<br/>• Interactive USDT Sizing Calculator"]
        D_CHART["Active Candlestick Canvas<br/>• EMA 12/26 & Volume Profile<br/>• Dynamic Trigger/Stop Overlays"]
        D_SCANNER["Responsive 1/2/4-Col Signal Scanner<br/>• Non-Color Cues (🛑, ⏳, 📈)<br/>• Factor Decomposition Drawers"]
        D_ACCORDION["Collapsible Macro Dossier<br/>• Fear & Greed • Mayer Cycle • Token Thesis"]
    end

    %% Pipeline Data Flows
    B_REST --> VAL_SCHEMA
    F_HIST --> BIAS_GUARD
    RSS_EXT --> VAL_SCHEMA
    MACRO_EXT --> VAL_SCHEMA

    VAL_SCHEMA --> BIAS_GUARD
    BIAS_GUARD --> IND_ENGINE
    BIAS_GUARD --> LIQ_ENGINE
    
    IND_ENGINE --> RR_ENGINE
    LIQ_ENGINE --> RR_ENGINE
    IND_ENGINE --> DCA_ENGINE

    RR_ENGINE --> ORCH
    LIQ_ENGINE --> ORCH

    ORCH <--> DATA_A
    ORCH <--> SEC_A
    ORCH <--> PROTO_A
    ORCH <--> QUANT_A
    ORCH <--> UX_A

    ORCH --> API_SRV
    ORCH --> MCP_PIPE
    ORCH -.->|"Signed Trade Intent (IPC)"| IPC_GATE

    API_SRV --> D_HERO
    API_SRV --> D_CHART
    API_SRV --> D_SCANNER
    API_SRV --> D_ACCORDION
```

---

## 3. System Data Architecture Diagram

```mermaid
graph TB
    subgraph CLIENT_LAYER["PRESENTATION & WORKSPACE TIER"]
        UI_HERO["Unified Decision Terminal<br/>(Above-the-Fold Fact Matrix)"]
        UI_CANVAS["HTML5 Dynamic Canvas Engine<br/>(Dual EMA Curves + Volume + Overlays)"]
        UI_SCAN["Responsive Scanner Grid<br/>(1-Col Phone | 2-Col Tablet | 4-Col Desktop)"]
        UI_MACRO["Collapsible Macro Accordion<br/>(Cycle / Mayer / Thesis / DCA)"]
    end

    subgraph API_TIER["API & DISPATCHING TIER (Starlette Async Gateway)"]
        HTTP_ROUTER["Starlette Async Router<br/>(Event Loop / Starlette ASGI)"]
        CACHE_STATE["In-Memory State & Polling Loop<br/>(5s Tickers | 15s Charts | 30s Signals | 60s Macro)"]
        DATA_SYNC["Relative Temporal Tracker<br/>(Per-Feed Age & Candle Close Countdown)"]
    end

    subgraph ORCHESTRATION_TIER["AGENT GOVERNANCE & DOCTRINE ENFORCEMENT TIER"]
        direction TB
        APEX_ORCH["Master Orchestrator Agent (kb://discipline Enforcement)"]
        
        subgraph SPECIALISTS["Specialized Sub-Agent Directory"]
            DATA_GUARD["🏗️ Data Engineering Agent<br/>(Ingestion Health, Cadence & Provenance)"]
            SEC_GUARD["🛡️ Security Guard Agent<br/>(Key Segregation & Zero-Trust Audit)"]
            PROTO_GUARD["⚡ MCP Protocol Agent<br/>(Pydantic FastMCP Contracts & Decimal Typing)"]
            QUANT_GUARD["📊 Quant & Risk Agent<br/>(Net R:R Math, Closed-Bar Audit, Depth Gate)"]
            UX_GUARD["🖥️ UX & Epistemic Agent<br/>(High-Density Design & Micro-Cap Formatting)"]
        end
    end

    subgraph COMPUTATION_TIER["QUANTITATIVE ENGINE & MODEL TIER"]
        SIG_ENGINE["Layer 4 Multi-Factor Engine<br/>(Trend, Momentum, MACD, %B, Lexicon)"]
        LIQ_AUDIT["Layer 2 Order Book Depth Engine<br/>(Touch Spread bps, ±1% Depth USDT, Thin Filter)"]
        DCA_SIM["DCA Backtester Engine<br/>(Historical Tranche Simulation & Fee Deductions)"]
        THESIS_EVAL["Layer 5 Token Value Framework<br/>(kb://frameworks/token-value 5 Questions)"]
    end

    subgraph BOUNDARY_TIER["SECURITY & REVERSIBLE PHYSICAL EXECUTION GATE"]
        MCP_SERVER["krmaazha-binance-mcp Process<br/>(Loads strictly BINANCE_READ_* keys)"]
        IPC_BRIDGE["Unix Domain Socket / Windows Named Pipe<br/>(Zero-Memory Shared IPC Socket)"]
        CONFIRMER["krmaazha-binance-mcp-confirmer Process<br/>(Loads strictly BINANCE_TRADE_* keys)"]
        HUMAN_OPERATOR{{"🧑‍💻 Physical Human Confirmation Gate<br/>(Manual Enter / Keypress Required)"}}
    end

    subgraph EXTERNAL_TIER["EXTERNAL SOURCES & PUBLIC EXCHANGES"]
        BINANCE_SPOT["Binance Spot Engine (REST/WS)"]
        BINANCE_FUTURES["Binance USD-M Futures Engine"]
        RSS_NEWS["Crypto News RSS Feeds"]
        MACRO_APIS["Macro Index Aggregators"]
    end

    %% Tier Connections
    CLIENT_LAYER <--> API_TIER
    API_TIER <--> ORCHESTRATION_TIER
    ORCHESTRATION_TIER <--> COMPUTATION_TIER
    ORCHESTRATION_TIER <--> BOUNDARY_TIER
    
    COMPUTATION_TIER <--> EXTERNAL_TIER
    BOUNDARY_TIER <--> BINANCE_SPOT
    BOUNDARY_TIER <--> HUMAN_OPERATOR
```

---

## 4. Deep-Dive Data Engineering Audit

### 4.1 Ingestion Pipeline & Rate Governance
* **Client Model**: Implemented in `src/krmaazha_binance_mcp/client.py` and `web_dashboard/app.py` via public anonymous REST initialization (`Client("", "")`). This ensures telemetry endpoints never consume authenticated API weight or expose API credentials to network snooping.
* **Weight Budgeting**: Order book depth queries (`limit=100`) consume a lightweight weight of 5 on Binance. Ticker summaries (`/api/v3/ticker/24hr`) are cached and batched across the watchlist symbols, preventing HTTP 429 IP bans.
* **Stream Resilience**: The frontend auto-polling engine in `dashboard.js` operates on tiered cadences:
  * **Tickers Ribbon**: 5,000ms
  * **Active Chart Klines**: 15,000ms
  * **Layer 4 Signals Scan**: 30,000ms
  * **Macro Market Structure**: 60,000ms
  * **Data Age Watchdog**: Relative temporal updates execute every 1,000ms, displaying exact elapsed intervals (e.g. `(3s ago)`).

### 4.2 Mathematical Integrity & Bias Elimination
* **Zero-Lookahead Windowing**:
  All technical indicators in `src/krmaazha_binance_mcp/indicators.py` enforce strictly closed-bar computation. For an active timeframe of 1h, indicator values are derived from candle $t$ (closed at $T$). Simulated execution entries and triggers are strictly anchored to the opening tick of candle $t+1$.
* **Survivorship-Bias-Free Futures**:
  Audits across the 986 USD-M futures universe (`src/krmaazha_binance_mcp/futures/`) incorporate historical delisted pairs, preventing the upward performance skew common in retail backtesters that only evaluate surviving tokens.
* **Trigger-Anchored Net R:R Accounting**:
  Retail systems calculate reward-to-risk from the current floating quote ($Q$), producing phantom edges. This system computes Net R:R strictly from the observable breakout **Trigger Price** ($T$), invalidation stop ($S$), and target ($P$), explicitly factoring in full round-trip friction ($F$):
  $$\text{Gross Risk \%} = \frac{|T - S|}{T} \times 100, \quad \text{Gross Reward \%} = \frac{|P - T|}{T} \times 100$$
  $$\text{Total Friction \%} = \frac{\text{Taker Fee (20.0 bps)} + \text{Touch Spread (bps)} + \text{Est. Slippage (5.0 bps)}}{10,000} \times 100$$
  $$\text{Net R:R} = \frac{\text{Gross Reward \%} - \text{Total Friction \%}}{\text{Gross Risk \%} + \text{Total Friction \%}}$$
  *Verified*: For `NOMUSDT` with $T=\$0.002374$, $S=\$0.002310$, $P=\$0.002523$, and $28.4\text{ bps}$ friction, this yields **$2.01:1 \approx 2.0:1$** (not $2.23:1$).

### 4.3 Schema Enforcement & Decimal Precision
* **FastMCP Typing**: All financial quantities across tools and models are encapsulated using Python's standard `Decimal` class (`src/krmaazha_binance_mcp/models.py`). Floating-point binary representation errors (e.g. `0.1 + 0.2 = 0.30000000000000004`) are banned.
* **Sub-Dollar Micro-Cap Formatting**: Low-value altcoins (`NOM`, `RESOLV`, `XVG`) are formatted with up to 6–8 decimal places (`$0.002340`) across both canvas charts and data tables.
* **Missing Metric Safeguards**:
  * Neutral signals returning `None` for ATR stops/targets are mapped to `"None (Awaiting Breakout)"` rather than formatting as `$0.00000000`.
  * Tokens with less than 200 days of trading history display `"N/A (< 200d history)"` for the 200-day SMA and Mayer Multiple rather than an inaccurate zero reading.

### 4.4 Defense-in-Depth Security Architecture
* **OS Process Isolation**:
  The MCP server (`src/krmaazha_binance_mcp/server.py`) executes in an unprivileged runtime with access limited strictly to `BINANCE_READ_*` environment variables.
* **Physical Execution Gate**:
  Trade submission capabilities reside exclusively in the separate `src/krmaazha_binance_mcp_confirmer/` process. The MCP server can only emit a serialized `CanonicalOrder` over a local Unix domain socket / named pipe. Order execution requires an explicit physical confirmation input from the human operator. Automated execution bypasses are prevented by design.

---

## 5. Senior Data Engineering Recommendations for Production Scale

1. **Redis / Dragonfly In-Memory Caching Layer**:
   * Introduce an async Redis Pub/Sub buffer. A single daemon process should ingest Binance WebSocket streams (`<symbol>@depth20@100ms` and `<symbol>@kline_1h`) and broadcast to local memory, dropping REST round-trip latency from ~180ms to <2ms.
2. **Circuit Breakers & Exponential Backoff**:
   * Wrap exchange client calls in a token-bucket rate limiter with circuit breakers that automatically switch to cached snapshots during Binance API degradation.
3. **Parquet Time-Series Archive**:
   * Persist partitioned Apache Parquet files (`data/klines/<symbol>/<year>.parquet`) for rapid historical lookups and zero-network backtesting.
4. **Epistemic Telemetry Provenance Headers**:
   * Every response payload includes epistemic classifications (`[OBSERVED FACT]`, `[CALCULATED ESTIMATE]`, `[AUTHORIZATION]`, and `[UNVALIDATED RAW FEED]`), guaranteeing transparent user trust.
