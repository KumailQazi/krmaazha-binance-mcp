# Senior Data & AI Engineer Interview Preparation Guide

An institutional technical interview guide based on the architectural patterns, data engineering invariants, and zero-trust AI mechanisms of **Krmaazha Binance MCP** ([`engineering/tech_stack_and_architecture.md`](file:///c:/Users/Raza/Downloads/konnextBinMcp/engineering/tech_stack_and_architecture.md)).

---

## 1. Interview Value Proposition

This architecture demonstrates senior-to-staff level competencies that distinguish production-grade systems from trivial AI wrappers:

1. **Non-Deterministic LLM Safety**: Treating the AI as an *untrusted reasoning co-pilot* with physical and cryptographic isolation from capital movement.
2. **Temporal Data Integrity**: Eliminating **lookahead bias** (closed-bar gating) and **survivorship bias** (retaining delisted assets).
3. **Financial Precision**: Overcoming IEEE-754 floating-point drift and JSON decimal serialization traps on micro-cap prices.
4. **Resilient Micro-Architecture**: Inter-process communication contracts, token-bucket rate budgeting, and cryptographic idempotency.

---

## 2. High-Signal Interview Questions & Answers

### Domain 1: AI Systems, Orchestration & Safety

#### Q1: "How do you safely connect an autonomous LLM or Multi-Agent system to real-world financial or irreversible transactional APIs?"
* **The Core Vulnerability**: Prompt injections, model hallucination, and probabilistic variance can lead to catastrophic capital loss if the model holds direct write API credentials.
* **Architectural Solution**:
  * **Dual-Process Separation**: The MCP server (`krmaazha-binance-mcp`) runs with read-only keys (`BINANCE_READ_*`).
  * **Zero Execution Authority**: The LLM *cannot* execute trades; it can only propose an immutable [`CanonicalOrder`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/models.py#L41) schema.
  * **Human-in-the-Loop Isolation**: Trading credentials (`BINANCE_TRADE_*`) reside solely in an isolated daemon (`krmaazha-binance-mcp-confirmer`). Execution requires a physical, human OS/Web confirmation click over a local Unix loopback socket.

#### Q2: "LLMs often generate hallucinations with high perceived confidence. How do you govern LLM reasoning in an institutional decision pipeline?"
* **The Core Vulnerability**: Models blend verified on-chain facts with speculative opinions, leading users or automated systems to treat guesses as truth.
* **Architectural Solution**:
  * **Epistemic Classification Tags**: Every model output must prefix its claims:
    * `[VERIFIED]`: Exchange-attested or on-chain ground truth (e.g., closed candle, order book depth).
    * `[ESTIMATED]`: Parametric quantitative models (e.g., ATR stop level, RSI).
    * `[OPINION]`: Macro thesis, market narratives, sentiment.
  * **Deterministic Knowledge Grounding**: Models are bound by hard doctrine in MCP resources ([`kb://discipline`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/knowledge/__init__.py)) rather than latent weights.
  * **Standardized Bottom-Line Synthesis**: Enforces an unambiguous closing contract:
    > *"At [timestamp], [instrument] is [state]. Setup valid only if [condition]; invalidated by [condition]. Costs/risks: [items]. Otherwise, no trade."*

---

### Domain 2: Data Engineering & Pipeline Integrity

#### Q3: "How do you eliminate lookahead bias in real-time streaming and backtesting feature pipelines?"
* **The Core Vulnerability**: Feature engines frequently consume the currently active candle $t$. Because candle $t$'s close, high, and low fluctuate until the interval ends, backtests generate unrealistic alpha that collapses in live execution.
* **Architectural Solution**:
  * **Closed-Bar Gating**: In [`signals/engine.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/signals/engine.py), all indicator arrays explicitly slice `[:-1]`.
  * **Strict Execution Timing**: Any signal computed on bar $t$ (which closed at $t$) is only valid for execution at open $t+1$. Intra-candle ticks are strictly disallowed from triggering deterministic strategy logic.

#### Q4: "What is survivorship bias in historical financial datasets, and how do you build pipelines to prevent it?"
* **The Core Vulnerability**: Backtesting only on currently active symbols filters out failed, collapsed, or delisted assets, artificially inflating model performance.
* **Architectural Solution**:
  * **Exhaustive Raw Ingestion**: In [`futures/data.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/futures/data.py), the ingestion pipeline audits **986 USD-M pairs** from raw Binance Vision archives, explicitly preserving **306 delisted perpetuals**.
  * **Schema Drift Handling**: The ingestion layer handles historical schema divergence (such as pre-2020 unheadered CSV dumps) deterministically offline without network calls at import time.

#### Q5: "How do you design rate-limiting and resilience when ingesting from high-frequency external gateways?"
* **The Core Vulnerability**: Exchange REST gateways impose hard rate limits (e.g., 1200 weight/minute); breaching them results in IP bans, while public secondary feeds degrade unpredictably.
* **Architectural Solution**:
  * **Token Bucket Throttling**: A stateful token bucket dynamically tracks endpoint weight costs against the 1200 weight/minute budget before making network calls.
  * **Graceful Per-Source Degradation**: Non-critical secondary signals (e.g., CoinGecko, Fear & Greed) degrade gracefully into fallback states without failing the primary pipeline.

---

### Domain 3: Numerical Stability, Types & Systems Design

#### Q6: "Why is standard IEEE-754 floating-point (`float`) prohibited in transactional data systems, and what serialization traps occur when replacing it?"
* **The Core Vulnerability**: Standard floats suffer from binary representation rounding errors (`0.1 + 0.2 = 0.30000000000000004`), violating exchange `LOT_SIZE` and `MIN_NOTIONAL` filters. However, standard stringification of Python `Decimal("0.00000000")` yields scientific notation (`"0E-8"`), causing JSON schema validators to fail.
* **Architectural Solution**:
  * **Zero-Float Policy**: All quantities, notionals, and sub-cent micro-cap prices ($0.002452$) use Python `Decimal`.
  * **Custom Pydantic Serializer**: Enforces [`PlainDecimal`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/models.py#L23) via `PlainSerializer(lambda v: format(v, "f"))`. This guarantees pure positional notation across the wire without floating-point artifacts or scientific exponential notation.

#### Q7: "How do you protect the IPC channel between an AI agent and execution systems from prompt injections or replay attacks?"
* **The Core Vulnerability**: Malicious prompt injections into an LLM could formulate destructive shell commands or duplicate order dispatches during network hiccups.
* **Architectural Solution**:
  * **Strict Data Contract**: The IPC channel transports only the strongly-typed [`CanonicalOrder`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/models.py#L41) Pydantic model with strict field regex validation (`^[A-Z0-9]{2,20}$`), preventing command/script injection.
  * **Cryptographic Idempotency**: Each intent generates an SHA-256 idempotency hash in [`idempotency.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/idempotency.py), guaranteeing that duplicate or replayed packets cannot produce duplicate executions.

---

## 3. Interview Competency & Architectural Mapping Matrix

| Interview Competency | The Architectural Solution in Krmaazha MCP | Key Metric / Invariant | Relevant Files |
|---|---|---|---|
| **AI Safety & Isolation** | Asymmetric Dual-Process with Physical Human Gate | LLM holds 0 trade keys; physical click required | [`server.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/server.py), [`executor.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp_confirmer/executor.py) |
| **Feature Engineering** | Closed-Bar Gating ($[:-1]$ slicing) | Zero lookahead bias | [`signals/engine.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/signals/engine.py) |
| **Data Ingestion** | Full Universe Ingestion including delisted perpetuals | Zero survivorship bias across 986 pairs | [`futures/data.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/futures/data.py) |
| **Numerical Accuracy** | `PlainDecimal` + Positional String Serialization | Zero float drift; handles 6+ decimal micro-caps | [`models.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/models.py) |
| **Security & Idempotency** | IPC Canonical Contracts + SHA-256 Hashes | Immune to command injection & duplicate replays | [`ipc.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/ipc.py), [`idempotency.py`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/idempotency.py) |
| **Reliability & Testing** | Pytest coverage gate & strict static typing | $\ge 90\%$ test coverage gate enforced | [`pyproject.toml`](file:///c:/Users/Raza/Downloads/konnextBinMcp/pyproject.toml) |
